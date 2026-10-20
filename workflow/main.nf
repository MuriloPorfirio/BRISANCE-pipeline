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

def annotationResources(value) {
    if (!value || !value.toString().startsWith('/')) {
        error '--vep_cache_dir must be an absolute local directory.'
    }
    def cache = file(value)
    if (!java.nio.file.Files.isDirectory(cache) || !java.nio.file.Files.isReadable(cache)) {
        error "Missing or unreadable VEP cache directory: ${value}"
    }
    cache = cache.toRealPath()
    if (!(cache.toString() ==~ '/[A-Za-z0-9_./-]+')) {
        error '--vep_cache_dir must use a simple absolute path without whitespace, quotes or commas.'
    }
    def info = cache.resolve('homo_sapiens/113_GRCh38/info.txt')
    if (!java.nio.file.Files.isRegularFile(info) || !java.nio.file.Files.isReadable(info) || info.size() == 0) {
        error "Missing, unreadable or empty VEP 113 GRCh38 cache metadata: ${info}"
    }
    def lines = java.nio.file.Files.readAllLines(info)
    if (!lines.any { line -> line ==~ /species[ \t]+homo_sapiens[ \t]*/ } ||
        !lines.any { line -> line ==~ /assembly[ \t]+GRCh38[ \t]*/ }) {
        error 'VEP cache info.txt must identify species homo_sapiens and assembly GRCh38.'
    }
    // Do not stage/copy or recursively hash the large shared cache.
    // Its info.txt is tracked; payload changes require an explicit fresh run.
    return [cache_dir: cache.toString(), info: info.toRealPath()]
}

def requireResource(value) {
    def resource = file(value)
    if (!java.nio.file.Files.isRegularFile(resource) || !java.nio.file.Files.isReadable(resource) || resource.size() == 0) {
        error "Missing, unreadable or empty alignment resource: ${value}"
    }
    if (!(resource.name ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/)) {
        error "Unsupported resource basename: ${resource.name}"
    }
    return resource.toRealPath()
}

def alignmentResources(referenceValue, knownDirValue, devicesValue) {
    def text = devicesValue?.toString()
    if (!text || !(text ==~ /[0-9]+(,[0-9]+)*/)) {
        error 'Provide --gpu_devices as three comma-separated GPU indices, e.g. 7,6,5.'
    }
    def devices = text.split(',').collect { it.toInteger() }
    if (devices.size() != 3 || devices.toSet().size() != 3) {
        error 'This alignment configuration requires three distinct GPU indices.'
    }
    def reference = requireResource(referenceValue)
    if (!reference.name.endsWith('.fasta')) {
        error '--reference must point to the uncompressed .fasta used in the historical run.'
    }
    def indexFiles = ['.fai', '.amb', '.ann', '.bwt', '.pac', '.sa'].collect { suffix ->
        requireResource("${referenceValue}${suffix}")
    }
    indexFiles.add(requireResource(reference.parent.resolve(reference.name.replaceFirst(/\.fasta$/, '.dict'))))
    def knownNames = [
        'Mills_and_1000G_gold_standard.indels.hg38.vcf.gz',
        'Homo_sapiens_assembly38.known_indels.vcf.gz',
        '1000G_phase1.snps.high_confidence.hg38.vcf.gz'
    ]
    def knownFiles = knownNames.collect { name -> requireResource("${knownDirValue}/${name}") }
    def knownIndices = knownNames.collect { name -> requireResource("${knownDirValue}/${name}.tbi") }
    return [reference: reference, indices: indexFiles, known: knownFiles, known_indices: knownIndices, devices: devices]
}

def recalibrationDevice(value, alignmentDevices) {
    def text = value == null ? alignmentDevices[0].toString() : value.toString()
    if (!(text ==~ /[0-9]+/) || !(text.toInteger() in alignmentDevices)) {
        error '--bqsr_gpu_device must be one of the GPU indices provided in --gpu_devices.'
    }
    return text.toInteger()
}

def callingDevices(value, alignmentDevices) {
    def text = value == null ? alignmentDevices.take(2).join(',') : value.toString()
    if (!(text ==~ /[0-9]+(,[0-9]+)*/)) {
        error '--caller_gpu_devices must contain two comma-separated GPU indices.'
    }
    def devices = text.split(',').collect { it.toInteger() }
    if (devices.size() != 2 || devices.toSet().size() != 2 || !alignmentDevices.containsAll(devices)) {
        error '--caller_gpu_devices requires two distinct indices from --gpu_devices.'
    }
    return devices
}

def tumorNormalInputs(items) {
    if (items.size() != 2 || items.count { it[1] == 'tumor' } != 1 || items.count { it[1] == 'normal' } != 1) {
        error 'MutectCaller requires exactly one adjusted tumor BAM and one adjusted normal BAM, with indexes.'
    }
    def tumor = items.find { it[1] == 'tumor' }
    def normal = items.find { it[1] == 'normal' }
    if (tumor[0] == normal[0]) {
        error 'Tumor and normal sample identifiers must be distinct.'
    }
    return tuple(tumor[0], tumor[2], tumor[3], normal[0], normal[2], normal[3])
}

def validateRows(rows) {
    if (!rows) {
        error 'The samplesheet has no data rows.'
    }
    def expectedColumns = ['sample', 'role', 'pair_id', 'fastq_1', 'fastq_2'].sort()
    def records = rows.collect { row ->
        if (row.keySet().toList().sort() != expectedColumns) {
            error 'Expected CSV columns: sample,role,pair_id,fastq_1,fastq_2.'
        }
        def sample = row.sample?.trim()
        def role = row.role?.trim()
        def pairId = row.pair_id?.trim()
        if (!sample || !(sample ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/)) {
            error "Invalid sample identifier: ${sample}"
        }
        if (!(role in ['tumor', 'normal'])) {
            error "Invalid role for ${sample}: use tumor or normal."
        }
        if (!pairId || !(pairId ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/)) {
            error "Invalid pair_id: ${pairId}"
        }
        def reads = ['fastq_1', 'fastq_2'].collect { column ->
            def value = row[column]?.trim()
            if (!value || !value.startsWith('/')) {
                error "${pairId}: ${column} must be an absolute local path."
            }
            def read = file(value)
            if (!java.nio.file.Files.isRegularFile(read) || !java.nio.file.Files.isReadable(read) || read.size() == 0) {
                error "Missing, unreadable or empty FASTQ: ${value}"
            }
            if (!(read.name ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*\.(fastq|fq)\.gz/)) {
                error "Unsupported FASTQ name: ${read.name}"
            }
            return read.toRealPath()
        }
        if (reads[0] == reads[1] || reads[0].name == reads[1].name) {
            error "${pairId}: mates must be distinct files with distinct basenames."
        }
        return tuple(sample, role, pairId, reads[0], reads[1])
    }
    if (records.collect { it[2] }.unique().size() != records.size()) {
        error 'Duplicate pair_id in samplesheet.'
    }
    def allReads = records.collectMany { [it[3], it[4]] }
    if (allReads.unique().size() != 2 * records.size()) {
        error 'A FASTQ was reused in more than one pair.'
    }
    def roleSamples = records.groupBy { it[1] }
    if (roleSamples.keySet().toList().sort() != ['normal', 'tumor']) {
        error 'Provide both a tumor and a normal sample.'
    }
    roleSamples.each { role, items ->
        if (items.collect { it[0] }.unique().size() != 1) {
            error "Only one ${role} sample is supported in this initial workflow."
        }
    }
    if (records.collect { it[0] }.unique().size() != 2) {
        error 'Tumor and normal must have distinct sample identifiers.'
    }
    return records
}

workflow {
    if (!(params.mode in ['validate', 'trim', 'validate-align', 'align', 'bqsr', 'read-groups', 'call', 'filter', 'validate-annotate', 'annotate', 'finalize'])) {
        error '--mode must be validate, trim, validate-align, align, bqsr, read-groups, call, filter, validate-annotate, annotate or finalize.'
    }
    if (!(params.fastqc_heap.toString() ==~ /[1-9][0-9]*[mg]/)) {
        error '--fastqc_heap must be a positive Java heap size, e.g. 8g.'
    }
    def sheet = file(params.input, checkIfExists: true)
    def resources = params.mode in ['validate-align', 'align', 'bqsr', 'read-groups', 'call', 'filter', 'validate-annotate', 'annotate', 'finalize']
        ? alignmentResources(params.reference, params.known_sites_dir, params.gpu_devices)
        : null
    def recalDevice = params.mode in ['bqsr', 'read-groups', 'call', 'filter', 'validate-annotate', 'annotate', 'finalize']
        ? recalibrationDevice(params.bqsr_gpu_device, resources.devices)
        : null
    def callDevices = params.mode in ['call', 'filter', 'validate-annotate', 'annotate', 'finalize']
        ? callingDevices(params.caller_gpu_devices, resources.devices)
        : null
    def annotation = params.mode in ['validate-annotate', 'annotate', 'finalize']
        ? annotationResources(params.vep_cache_dir)
        : null
    def pairs = channel.of(sheet)
        .splitCsv(header: true)
        .collect()
        .map { rows -> validateRows(rows) }

    if (params.mode in ['validate', 'validate-align', 'validate-annotate']) {
        pairs.view { records ->
            def tumorPairs = records.count { it[1] == 'tumor' }
            def normalPairs = records.count { it[1] == 'normal' }
            def details = resources
                ? " Alignment resources found; configured GPU indices: ${resources.devices.join(',')}. No GPU availability check performed."
                : ''
            if (annotation) {
                details += " VEP cache metadata found: ${annotation.cache_dir}/homo_sapiens/113_GRCh38. Cache contents and container access not checked."
            }
            return "Validated ${records.size()} pairs: ${tumorPairs} tumor, ${normalPairs} normal. No FASTQ contents read; no processing started.${details}"
        }
    } else {
        TRIM_GALORE(
            pairs.flatMap { records -> records },
            params.fastqc_heap.toString(),
            file(params.outdir).toAbsolutePath().toString()
        )
        if (params.mode in ['align', 'bqsr', 'read-groups', 'call', 'filter', 'annotate', 'finalize']) {
            def bySample = TRIM_GALORE.out.reads
                .map { sample, role, pairId, r1, r2 -> tuple(tuple(sample, role), tuple(pairId, r1, r2)) }
                .groupTuple()
                .map { key, readPairs ->
                    def ordered = readPairs.toSorted { a, b -> a[0] <=> b[0] }
                    return tuple(key[0], key[1], ordered.collect { it[0] }, ordered.collect { it[1] }, ordered.collect { it[2] })
                }
            def alignOutput = params.align_outdir
                ? file(params.align_outdir).toAbsolutePath().toString()
                : file(params.outdir).toAbsolutePath().parent.resolve('stage2').toString()
            FQ2BAM(
                bySample,
                resources.reference,
                resources.indices,
                resources.known,
                resources.known_indices,
                [devices: resources.devices, thread_pool: 16, sort_memory_gb: 128],
                alignOutput
            )
            if (params.mode in ['bqsr', 'read-groups', 'call', 'filter', 'annotate', 'finalize']) {
                // Wait for BOTH fq2bam tasks; per-process maxForks alone
                // cannot prevent overlap between different GPU processes.
                def allAlignments = FQ2BAM.out.alignments
                    .join(FQ2BAM.out.indices, by: [0, 1], failOnDuplicate: true, failOnMismatch: true)
                    .collect(flat: false)
                    .flatMap { items ->
                        if (items.size() != 2 || items.collect { it[1] }.toSet() != ['tumor', 'normal'].toSet()) {
                            error 'ApplyBQSR requires the completed tumor and normal alignments.'
                        }
                        return items.toSorted { a, b -> a[0] <=> b[0] }
                            .collect { item -> tuple(item[0], item[1], item[2], item[5], item[3]) }
                    }
                def recalOutput = params.bqsr_outdir
                    ? file(params.bqsr_outdir).toAbsolutePath().toString()
                    : file(params.outdir).toAbsolutePath().parent.resolve('stage3').toString()
                APPLY_BQSR(
                    allAlignments,
                    resources.reference,
                    resources.indices,
                    [device: recalDevice, threads: 16],
                    recalOutput
                )
                if (params.mode in ['read-groups', 'call', 'filter', 'annotate', 'finalize']) {
                    def rgOutput = params.read_groups_outdir
                        ? file(params.read_groups_outdir).toAbsolutePath().toString()
                        : file(params.outdir).toAbsolutePath().parent.resolve('stage4').toString()
                    ADJUST_READ_GROUPS(APPLY_BQSR.out.recalibrated, rgOutput)
                    if (params.mode in ['call', 'filter', 'annotate', 'finalize']) {
                        // Wait for BOTH adjusted BAMs/indexes. Their upstream
                        // GPU tasks must have finished before calling starts.
                        def tumorNormal = ADJUST_READ_GROUPS.out.alignments
                            .collect(flat: false)
                            .map { items -> tumorNormalInputs(items) }
                        def callOutput = params.call_outdir
                            ? file(params.call_outdir).toAbsolutePath().toString()
                            : file(params.outdir).toAbsolutePath().parent.resolve('stage5').toString()
                        MUTECT_CALLER(
                            tumorNormal,
                            resources.reference,
                            resources.indices,
                            [devices: callDevices, htvc_threads: 24],
                            callOutput
                        )
                        if (params.mode in ['filter', 'annotate', 'finalize']) {
                            def filterOutput = params.filter_outdir
                                ? file(params.filter_outdir).toAbsolutePath().toString()
                                : file(params.outdir).toAbsolutePath().parent.resolve('stage6').toString()
                            COMPRESS_RAW_VCF(
                                MUTECT_CALLER.out.calls.map { tumor, normal, vcf, stats -> tuple(tumor, normal, vcf) },
                                filterOutput
                            )
                            def rawWithStats = COMPRESS_RAW_VCF.out.compressed.join(
                                MUTECT_CALLER.out.calls.map { tumor, normal, vcf, stats -> tuple(tumor, normal, stats) },
                                by: [0, 1], failOnDuplicate: true, failOnMismatch: true
                            )
                            FILTER_MUTECT_CALLS(
                                rawWithStats,
                                resources.reference,
                                resources.indices.findAll { index -> index.name.endsWith('.fai') || index.name.endsWith('.dict') },
                                filterOutput
                            )
                            SELECT_PASS(FILTER_MUTECT_CALLS.out.filtered, filterOutput)
                            if (params.mode in ['annotate', 'finalize']) {
                                def annotationOutput = params.annotation_outdir
                                    ? file(params.annotation_outdir).toAbsolutePath().toString()
                                    : file(params.outdir).toAbsolutePath().parent.resolve('stage7').toString()
                                ANNOTATE_VEP(
                                    SELECT_PASS.out.pass_calls,
                                    annotation.info,
                                    [cache_dir: annotation.cache_dir],
                                    annotationOutput
                                )
                                def annotationWithInput = ANNOTATE_VEP.out.annotated.join(
                                    SELECT_PASS.out.pass_calls.map { tumor, normal, vcf, index -> tuple(tumor, normal, vcf) },
                                    by: [0, 1], failOnDuplicate: true, failOnMismatch: true
                                )
                                INDEX_VEP(annotationWithInput, annotationOutput)
                                if (params.mode == 'finalize') {
                                    def finalOutput = params.final_outdir
                                        ? file(params.final_outdir).toAbsolutePath().toString()
                                        : file(params.outdir).toAbsolutePath().parent.resolve('stage8').toString()
                                    def indexedAnnotation = ANNOTATE_VEP.out.annotated.join(
                                        INDEX_VEP.out.indices,
                                        by: [0, 1], failOnDuplicate: true, failOnMismatch: true
                                    )
                                    SELECT_POSITIVE_TLOD(indexedAnnotation, finalOutput)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
