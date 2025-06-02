rule all:
    input:
        expand("results/{i}.txt", i=range(5)),


rule a:
    output:
        "results/{i}.txt",
    log:
        "logs/{i}.txt",
    shell:
        """
        if [ "{wildcards.i}" -eq 2 ]; then
            echo "Intentional failure for i=2" > {log}
            exit 1
        else
            echo "Success for i={wildcards.i}" > {log}
            echo {wildcards.i} > {output}
        fi
        """
