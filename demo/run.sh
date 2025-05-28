#!/usr/bin/env bash

# Define default values
WORKFLOWS_DIR="workflows"
RESULTS_DIR="results"
DEFAULT_ARGS="--cores 1 --logger snkmt --nolock"



# Find all Snakemake files
WORKFLOW_FILES=$(find "$WORKFLOWS_DIR" -name "*.smk")

if [ -z "$WORKFLOW_FILES" ]; then
    echo "No workflow files found in $WORKFLOWS_DIR"
    exit 1
fi

# Run each workflow in the background
for workflow in $WORKFLOW_FILES; do
    echo "Running $workflow"
    workflow_name=$(basename "$workflow" .smk)
    workflow_result_dir="$RESULTS_DIR/$workflow_name"
    snakemake -d "$workflow_result_dir" -s "$workflow" $DEFAULT_ARGS > /dev/null 2>&1 &
done


