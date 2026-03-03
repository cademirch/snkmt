#!/usr/bin/env bash
# Run all demo workflows in parallel, logging to the demo database
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKFLOWS_DIR="$SCRIPT_DIR/workflows"
RESULTS_DIR="$SCRIPT_DIR/results"
DB_PATH="$SCRIPT_DIR/db/snkmt.db"
DEFAULT_ARGS="--cores 1 --logger snkmt --logger-snkmt-db $DB_PATH --nolock"

# Clean up previous results
rm -rf "$RESULTS_DIR"

WORKFLOW_FILES=$(find "$WORKFLOWS_DIR" -name "*.smk" -not -path "*/.snakemake/*")
if [ -z "$WORKFLOW_FILES" ]; then
    echo "No workflow files found in $WORKFLOWS_DIR"
    exit 1
fi

for workflow in $WORKFLOW_FILES; do
    workflow_name=$(basename "$workflow" .smk)
    workflow_result_dir="$RESULTS_DIR/$workflow_name"
    echo "Running $workflow_name..."
    snakemake -d "$workflow_result_dir" -s "$workflow" $DEFAULT_ARGS > /dev/null 2>&1 &
done

echo "All demo workflows launched in background."
echo "Run 'snkmt console -d $DB_PATH' to monitor."
wait
echo "All demo workflows completed."
