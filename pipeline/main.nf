// Configurable entry point. The evaluated HG008 workflow/ tree is unchanged.
include { TRIM_GALORE } from './modules/trim_galore'
include { FQ2BAM } from './modules/fq2bam'
include { APPLY_BQSR } from './modules/apply_bqsr'
include { ADJUST_READ_GROUPS } from './modules/read_groups'
include { MUTECT_CALLER } from './modules/mutect_caller'
include { COMPRESS_RAW_VCF } from './modules/compress_raw_vcf'
include { FILTER_MUTECT_CALLS } from './modules/filter_mutect_calls'
include { SELECT_PASS } from './modules/select_pass'
include { ANNOTATE_VEP } from './modules/annotate_vep'
include { INDEX_VEP } from './modules/index_vep'
include { SELECT_POSITIVE_TLOD } from './modules/select_positive_tlod'
include { CHECK_INPUT_BAM } from './modules/check_input_bam'
include { COLLECT_BAM_QC } from './modules/collect_bam_qc'
include { CHECK_PREPARED_PON; PREPARE_PON_VCF; PREPON; POSTPON } from './modules/pon'
include { CHECK_CONTAMINATION_SITES; GET_PILEUP_SUMMARIES; CALCULATE_CONTAMINATION; LEARN_READ_ORIENTATION_MODEL } from './modules/somatic_models'

def safeValues(value) {
    // Defense in depth for generated parameters that enter task scripts.
    if (value instanceof Map) value.values().each { safeValues(it) }
    else if (value instanceof List) value.each { safeValues(it) }
    else if (value instanceof String) {
        if (!(value ==~ /[A-Za-z0-9_.,\/-]*/)) error 'Unsupported character in generated configuration.'
    } else if (value != null && !(value instanceof Integer) && !(value instanceof Long) && !(value instanceof Boolean)) {
        error 'Unsupported value in generated configuration.'
    }
}

def resource(value) {
    if (!value || !(value.toString() ==~ /\/[A-Za-z0-9_.\/-]+/)) error 'An absolute simple resource path is required.'
    def path = file(value, checkIfExists: true)
    if (!java.nio.file.Files.isRegularFile(path) || !java.nio.file.Files.isReadable(path) || path.size() == 0) {
        error "Missing, unreadable or empty resource: ${path}"
    }
    if (!(path.toRealPath().toString() ==~ /\/[A-Za-z0-9_.\/-]+/)) error 'Unsupported resolved resource path.'
    return path
}

def sampleRecords(rows) {
    if (!(rows instanceof List) || !rows) error 'No input pairs configured.'
    def records = rows.collect { row ->
        if (!(row.sample ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/) ||
            !(row.pair_id ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/) || !(row.role in ['tumor', 'normal'])) {
            error 'Invalid sample, pair identifier or role.'
        }
        return tuple(row.sample, row.role, row.pair_id, resource(row.fastq_1), resource(row.fastq_2))
    }
    if (records.collect { it[2] }.toSet().size() != records.size()) error 'Duplicate pair identifier.'
    if (records.collectMany { [it[3].toRealPath(), it[4].toRealPath()] }.toSet().size() != 2 * records.size()) {
        error 'A FASTQ is reused.'
    }
    def roles = records.groupBy { it[1] }
    if (roles.keySet().toSet() != ['tumor', 'normal'].toSet() ||
        roles.any { key, items -> items.collect { it[0] }.toSet().size() != 1 } ||
        records.collect { it[0] }.toSet().size() != 2) error 'Exactly one distinct tumor and normal sample are required.'
    return records
}

workflow {
    if (!(params.mode in ['validate', 'run'])) error 'Use the interface runner; modes are validate and run.'
    if (!params.configuration || !params.bundle || !params.images) error 'Use interface/run_brisance.sh to generate execution parameters.'
    def c = params.configuration
    safeValues(c)
    safeValues(params.bundle)
    if (c.schema_version != 1 || !(c.reference.assembly in ['GRCh38', 'GRCh37']) || c.reference.vep_cache_version != 113) {
        error 'Unsupported reference/configuration schema.'
    }
    params.images.each { key, value ->
        if (!(value ==~ /sha256:[0-9a-f]{64}/)) error 'Execution requires locally checked immutable Docker image IDs.'
    }
    def bamInput = c.get('input_mode', 'fastq') == 'bam'
    def records = bamInput ? c.samples.collect { row ->
        if (!(row.sample ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/) || !(row.role in ['tumor', 'normal'])) error 'Invalid BAM sample.'
        tuple(row.sample, row.role, resource(row.bam), resource(row.bam_index))
    } : sampleRecords(c.samples)
    def ref = resource(c.reference.fasta)
    def indices = params.bundle.reference_indices.collect { resource(it) }
    def sites = c.reference.known_sites.collect { resource(it) }
    def siteIndices = params.bundle.known_indices.collect { resource(it) }
    def cacheInfo = resource(params.bundle.cache_info)
    def res = c.resources
    def output = "${c.analysis_dir}/results"
    def orientation = c.get('orientation', [mode: 'off'])
    def contamination = c.get('contamination', [mode: 'off'])
    if (params.mode == 'validate') {
        log.info "CONFIGURABLE WORKFLOW CHECK OK: ${records.size()} input pairs; all stages loaded. No processing started."
    } else {
        def readyBams
        if (bamInput) {
            CHECK_INPUT_BAM(channel.fromList(records), indices.find { it.name.endsWith('.fai') }, output)
            readyBams = CHECK_INPUT_BAM.out.alignments
        } else {
        TRIM_GALORE(channel.fromList(records), "${res.trim.fastqc_heap_gb}g", c.trimming, "${output}/stage1")
        def bySample = TRIM_GALORE.out.reads
            .map { sample, role, pairId, r1, r2 -> tuple(tuple(sample, role), tuple(pairId, r1, r2)) }
            .groupTuple()
            .map { key, pairs ->
                def ordered = pairs.toSorted { a, b -> a[0] <=> b[0] }
                tuple(key[0], key[1], ordered.collect { it[0] }, ordered.collect { it[1] }, ordered.collect { it[2] })
            }
        FQ2BAM(bySample, ref, indices, sites, siteIndices,
            [devices: res.alignment.gpu_devices, thread_pool: res.alignment.bwa_thread_pool,
             sort_memory_gb: res.alignment.sorting_memory_gb], "${output}/stage2")
        // Explicit barrier: no recalibration until BOTH alignments have finished.
        def alignments = FQ2BAM.out.alignments
            .join(FQ2BAM.out.indices, by: [0, 1], failOnDuplicate: true, failOnMismatch: true)
            .collect(flat: false)
            .flatMap { items ->
                if (items.size() != 2) error 'Two complete alignments with indexes are required.'
                items.toSorted { a, b -> a[0] <=> b[0] }.collect { item -> tuple(item[0], item[1], item[2], item[5], item[3]) }
            }
        APPLY_BQSR(alignments, ref, indices,
            [device: res.bqsr.gpu_devices[0], threads: res.bqsr.threads], "${output}/stage3")
        ADJUST_READ_GROUPS(APPLY_BQSR.out.recalibrated, res.read_groups.index_threads, "${output}/stage4")
        readyBams = ADJUST_READ_GROUPS.out.alignments
        }
        if (c.get('qc', [:]).get('enabled', false)) {
            COLLECT_BAM_QC(readyBams, ref, indices, [device: res.calling.gpu_devices[0]], "${output}/qc")
            readyBams = readyBams.join(COLLECT_BAM_QC.out.metrics, by: [0, 1], failOnDuplicate: true, failOnMismatch: true)
                .map { sample, role, bam, bai, metrics -> tuple(sample, role, bam, bai) }
        }
        def tumorNormal = readyBams.collect(flat: false).map { items ->
            if (items.size() != 2) error 'Two adjusted BAMs with indexes are required.'
            def tumor = items.find { it[1] == 'tumor' }
            def normal = items.find { it[1] == 'normal' }
            tuple(tumor[0], tumor[2], tumor[3], normal[0], normal[2], normal[3])
        }
        def ponChannel = channel.value([])
        if (c.get('somatic', [:]).get('pon')) {
            def pon = resource(c.somatic.pon)
            def tbi = resource(c.somatic.pon + '.tbi')
            if (c.somatic.pon_prepared) {
                def index = resource(c.somatic.pon + '.pon')
                CHECK_PREPARED_PON(pon, tbi, index, ref, indices, output)
                ponChannel = CHECK_PREPARED_PON.out.receipt.map { receipt -> tuple(pon, tbi, index) }.first()
            } else {
                PREPARE_PON_VCF(pon, tbi, ref, indices, output)
                PREPON(PREPARE_PON_VCF.out.panel, res.calling.gpu_devices[0], output)
                ponChannel = PREPON.out.panel.first()
            }
        }
        MUTECT_CALLER(tumorNormal, ref, indices, ponChannel,
            [devices: res.calling.gpu_devices, htvc_threads: res.calling.threads,
             orientation_auto: orientation.mode == 'auto'], "${output}/stage5")
        def priorsChannel = channel.value([])
        if (orientation.mode == 'auto') {
            LEARN_READ_ORIENTATION_MODEL(MUTECT_CALLER.out.f1r2, res.filtering.java_heap_gb, output)
            // Missing F1R2 must fail, rather than close a branch without filtering.
            priorsChannel = LEARN_READ_ORIENTATION_MODEL.out.priors
                .ifEmpty { error 'Requested orientation model produced no F1R2/priors.' }
                .map { priors -> [priors] }
        } else if (orientation.mode == 'provided') {
            priorsChannel = channel.value([resource(orientation.priors)])
        }
        def contaminationChannel = channel.value([])
        def segmentationChannel = channel.value([])
        if (contamination.mode == 'auto') {
            CHECK_CONTAMINATION_SITES(resource(contamination.sites), resource(contamination.sites + '.tbi'), ref, indices, output)
            GET_PILEUP_SUMMARIES(readyBams, CHECK_CONTAMINATION_SITES.out.resource, ref, indices,
                res.filtering.java_heap_gb, output)
            def pileupPair = GET_PILEUP_SUMMARIES.out.pileups.collect(flat: false).map { items ->
                if (items.size() != 2) error 'Tumor and matched-normal pileups are required.'
                def tumor = items.find { it[1] == 'tumor' }
                def normal = items.find { it[1] == 'normal' }
                tuple(tumor[0], tumor[2], normal[0], normal[2])
            }
            CALCULATE_CONTAMINATION(pileupPair, res.filtering.java_heap_gb, output)
            contaminationChannel = CALCULATE_CONTAMINATION.out.model.map { table, segments -> [table] }
            segmentationChannel = CALCULATE_CONTAMINATION.out.model.map { table, segments -> [segments] }
        } else if (contamination.mode == 'provided') {
            contaminationChannel = channel.value([resource(contamination.table)])
            if (contamination.get('segments')) segmentationChannel = channel.value([resource(contamination.segments)])
        }
        def calls = MUTECT_CALLER.out.calls
        if (c.get('somatic', [:]).get('pon')) {
            POSTPON(calls, ponChannel, res.calling.gpu_devices[0], "${output}/stage5")
            calls = POSTPON.out.calls
        }
        COMPRESS_RAW_VCF(calls.map { tumor, normal, vcf, stats -> tuple(tumor, normal, vcf) }, "${output}/stage6")
        def rawWithStats = COMPRESS_RAW_VCF.out.compressed.join(
            calls.map { tumor, normal, vcf, stats -> tuple(tumor, normal, stats) },
            by: [0, 1], failOnDuplicate: true, failOnMismatch: true)
        FILTER_MUTECT_CALLS(rawWithStats, ref, indices.findAll { it.name.endsWith('.fai') || it.name.endsWith('.dict') },
            priorsChannel, contaminationChannel, segmentationChannel,
            res.filtering.java_heap_gb, "${output}/stage6")
        SELECT_PASS(FILTER_MUTECT_CALLS.out.filtered, "${output}/stage6")
        ANNOTATE_VEP(SELECT_PASS.out.pass_calls, cacheInfo,
            [cache_dir: c.reference.vep_cache_dir, assembly: c.reference.assembly,
             cache_version: c.reference.vep_cache_version, forks: res.annotation.forks], "${output}/stage7")
        def annotationWithInput = ANNOTATE_VEP.out.annotated.join(
            SELECT_PASS.out.pass_calls.map { tumor, normal, vcf, index -> tuple(tumor, normal, vcf) },
            by: [0, 1], failOnDuplicate: true, failOnMismatch: true)
        INDEX_VEP(annotationWithInput, "${output}/stage7")
        def indexed = ANNOTATE_VEP.out.annotated.join(INDEX_VEP.out.indices,
            by: [0, 1], failOnDuplicate: true, failOnMismatch: true)
        SELECT_POSITIVE_TLOD(indexed, "${output}/stage8")
    }
}
