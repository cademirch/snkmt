from loguru import logger

# Disable loguru logging by default for the snkmt namespace.
# This prevents debug messages from leaking to stderr when snkmt is imported
# as a library (e.g., by the snakemake logger plugin) rather than run via the CLI.
# The CLI's verbose_callback re-enables logging when snkmt is used directly.
logger.disable("snkmt")
