#!/usr/bin/env python3

import os
import sys

def parse_summary_file(path):
    """Lê os arquivos summary.txt (passos 04 e 05) e extrai as métricas."""
    data = {}
    if not os.path.exists(path):
        print(f"AVISO: Arquivo não encontrado: {path}")
        return None
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=")
                data[key] = val
    return data

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 06_build_summary_table.py <output_dir_04> <output_dir_05> <final_output_tsv>")
        sys.exit(1)

    dir_snps = sys.argv[1]
    dir_indels = sys.argv[2]
    output_file = sys.argv[3]

    # Caminhos para os arquivos de sumário gerados nos passos 4 e 5
    summary_snps_path = os.path.join(dir_snps, "summary.txt")
    summary_indels_path = os.path.join(dir_indels, "summary.txt")

    summary_snps = parse_summary_file(summary_snps_path)
    summary_indels = parse_summary_file(summary_indels_path)

    if not summary_snps or not summary_indels:
        print("ERRO: Não foi possível carregar os dados de entrada. Verifique os diretórios.")
        sys.exit(1)

    # Colunas da tabela final
    headers = [
        "Metric", "SNPs_Value", "InDels_Value"
    ]

    # Mapeamento de linhas que queremos na tabela final
    rows_to_extract = [
        ("Total CLARA", "clara_total"),
        ("Total DRAGEN", "dragen_total"),
        ("Shared (Concordant)", "shared"),
        ("Shared %", "shared_pct"),
        ("Exclusive CLARA", "clara_only"),
        ("Exclusive CLARA %", "clara_only_pct"),
        ("Exclusive DRAGEN", "dragen_only"),
        ("Exclusive DRAGEN %", "dragen_only_pct"),
        ("Union Total", "union_total")
    ]

    try:
        with open(output_file, "w", encoding="utf-8") as out:
            out.write("\t".join(headers) + "\n")
            for label, key in rows_to_extract:
                val_snp = summary_snps.get(key, "N/A")
                val_indel = summary_indels.get(key, "N/A")
                out.write(f"{label}\t{val_snp}\t{val_indel}\n")
        
        print(f"\n[INFO] Tabela consolidada criada com sucesso: {output_file}")
        print("-" * 50)
        # Print rápido no terminal para conferência
        print(f"{'Métrica':<25} | {'SNPs':<12} | {'InDels':<12}")
        print("-" * 50)
        for label, key in rows_to_extract:
            print(f"{label:<25} | {summary_snps.get(key, 'N/A'):<12} | {summary_indels.get(key, 'N/A'):<12}")
        print("-" * 50)

    except Exception as e:
        print(f"ERRO ao gravar arquivo final: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
