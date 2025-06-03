# snkmt

A CLI utility for monitoring running Snakemake workflows in real-time.

> **Note**: This project is still under active development. Please report bugs, weird UI behavior, and feature requests - they are greatly appreciated!

## Overview

snkmt (Snakemate) works with the `snakemake-logger-plugin-snkmt` plugin to capture and store Snakemake workflow execution data in a SQLite database. This allows you to monitor workflow progress, view job statuses, and troubleshoot errors through an interactive terminal interface.

## How it Works

1. The `snakemake-logger-plugin-snkmt` plugin captures workflow events during Snakemake execution
2. Events are written to a local SQLite database 
3. snkmt provides tools to view and monitor this data through a terminal UI and CLI commands

## Installation

Install via the logger plugin (recommended):

```bash
pip install snakemake-logger-plugin-snkmt
```

This will automatically install snkmt as a dependency.

## Usage

### Execute a Snakemake workflow

```bash
snakemake --logger snkmt ...
```

### Interactive Console

Launch the real-time monitoring interface:

- `Tab` / `Shift+Tab`: Navigate between interface elements
- `Enter`: Select workflow rows or log files
- `Escape`: Close modals/dialogs
- `q` / `Ctrl+C`: Quit application

```bash
snkmt console
```

Options:
- `--db-path, -d`: Specify custom database path

### Database Commands

View database information:
```bash
snkmt db info [DB_PATH]
```

Migrate database to latest version:
```bash
snkmt db migrate [DB_PATH]
```

## Configuration

By default, snkmt stores data in the [XDG Base Directory](https://specifications.freedesktop.org/basedir-spec/latest/) specified user data directory. You can customize this location using the `--db-path` option or by configuring the logger plugin.


## Screenshots

### Main Dashboard
<img src="docs/screenshots/dashboard.png" alt="snkmt dashboard showing workflow list and details" width="800">

### Error Inspection
<img src="docs/screenshots/failedjob_dropdown.png" alt="Error view showing failed jobs and log files" width="800">

<img src="docs/screenshots/logfile_modal.png" alt="Error view showing failed jobs and log files" width="800">
