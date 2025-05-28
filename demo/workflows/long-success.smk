import random


rule all:
    input:
        expand("results/final_{sample}.txt", sample=range(40)),
        "results/summary.txt",


rule generate_data:
    output:
        data="results/data_{sample}.txt",
    threads: 2
    resources:
        mem_mb=500,
        runtime=10,
    shell:
        """
        sleep $(gshuf -i 1-5 -n 1)
        echo "Sample {wildcards.sample} data: $RANDOM" > {output.data}
        """


rule process_data:
    input:
        data="results/data_{sample}.txt",
    output:
        processed="results/processed_{sample}.txt",
    threads: 4
    resources:
        mem_mb=1000,
        runtime=20,
    shell:
        """
        sleep $(gshuf -i 3-8 -n 1)
        cat {input.data} | tr '[a-z]' '[A-Z]' > {output.processed}
        echo "PROCESSED ON: $(date)" >> {output.processed}
        """


rule finalize:
    input:
        processed="results/processed_{sample}.txt",
    output:
        final="results/final_{sample}.txt",
    threads: 1
    resources:
        mem_mb=200,
        runtime=5,
    shell:
        """
        sleep $(gshuf -i 1-3 -n 1)
        cat {input.processed} > {output.final}
        echo "FINALIZED: $(date)" >> {output.final}
        """


rule summarize:
    input:
        finals=expand("results/final_{sample}.txt", sample=range(5)),
    output:
        summary="results/summary.txt",
    threads: 8
    resources:
        mem_mb=2000,
        runtime=30,
    shell:
        """
        sleep 1
        echo "Summary of all samples" > {output.summary}
        cat {input.finals} | grep -v FINALIZED | grep -v PROCESSED >> {output.summary}
        echo "Created on: $(date)" >> {output.summary}
        """
