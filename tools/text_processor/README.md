# Ollama Text Processor

A versatile Python tool for processing text files using Ollama's language models. Supports multiple input sources including local files, directories, S3 buckets, ZIP archives, and can chain operations by processing its own JSONL output.

## Features

- **Multiple Input Sources**:
  - Local files and directories
  - S3 buckets (`s3://bucket/prefix/`)
  - ZIP archives
  - Glob patterns (`*.txt`, `docs/*.md`)
  - JSONL output from previous runs (for chaining operations)

- **Flexible Processing**:
  - Built-in operations: summarize, analyze, extract
  - Custom prompts with `{text}` placeholder
  - Batch processing of multiple files
  - Configurable file extensions

- **Output Formats**:
  - Standard JSON (structured with full metadata)
  - JSONL (one result per line, ideal for streaming and chaining)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull a model
ollama pull llama3.2
```

## Basic Usage

### Single File Processing
```bash
python text_processor_enhanced.py sample.txt --summarize
```

### Directory Processing
```bash
# Process all text files in a directory
python text_processor_enhanced.py /path/to/docs/ --analyze

# Non-recursive (current directory only)
python text_processor_enhanced.py ./logs/ --no-recursive --extract
```

### Custom Prompts
```bash
python text_processor_enhanced.py textfiles/ -p "Extract all dates mentioned: {text}" -o dates.jsonl --jsonl
```

### S3 Bucket Processing
```bash
# Process files from S3 (requires AWS credentials)
python text_processor_enhanced.py s3://my-bucket/documents/ --summarize -o results.json
```

### ZIP Archive Processing
```bash
python text_processor_enhanced.py archive.zip --analyze -o analysis.jsonl --jsonl
```

## Advanced Usage: Chaining Operations

The `--input-jsonl` flag enables powerful multi-stage analysis pipelines:

```bash
# Step 1: Extract locations from multiple documents
python text_processor_enhanced.py textfiles/ \
  -p "Extract all location names mentioned: {text}" \
  -o locations.jsonl --jsonl

# Step 2: Analyze all locations together
python text_processor_enhanced.py locations.jsonl --input-jsonl \
  -p "Categorize these locations by continent and type: {text}" \
  -o categorized.jsonl --jsonl

# Step 3: Generate a summary report
python text_processor_enhanced.py categorized.jsonl --input-jsonl \
  -p "Create a travel guide summary from this data: {text}" \
  -o travel_guide.jsonl --jsonl
```

## Command Line Options

```
positional arguments:
  source                Source: S3 path, zip file, directory, or file pattern

optional arguments:
  -h, --help            Show help message
  -m, --model MODEL     Ollama model to use (default: llama3.2)
  -p, --prompt PROMPT   Custom prompt template (use {text} as placeholder)
  -o, --output OUTPUT   Output file for results
  --jsonl               Output in JSONL format (one result per line)
  --input-jsonl         Input is a JSONL file from previous processing
  --summarize           Summarize the text
  --analyze             Analyze the text
  --extract             Extract key information
  -e, --extensions      File extensions to process (default: .txt .md .log .csv)
  --no-recursive        Don't recursively search directories
```

## Examples

### Research Pipeline
```bash
# Extract key findings from research papers
python text_processor_enhanced.py papers/ \
  -p "Extract methodology and key findings: {text}" \
  -e .txt .pdf \
  -o findings.jsonl --jsonl

# Synthesize all findings
python text_processor_enhanced.py findings.jsonl --input-jsonl \
  -p "Identify common methodologies and conflicting results: {text}" \
  -o synthesis.jsonl --jsonl
```

### Log Analysis
```bash
# Extract errors from logs
python text_processor_enhanced.py /var/logs/ \
  -p "Extract error messages and timestamps: {text}" \
  -e .log \
  -o errors.jsonl --jsonl

# Analyze error patterns
python text_processor_enhanced.py errors.jsonl --input-jsonl \
  -p "Group errors by type and identify root causes: {text}" \
  -o error_analysis.jsonl --jsonl
```

### Content Processing
```bash
# Summarize blog posts
python text_processor_enhanced.py blog_posts/ --summarize -o summaries.jsonl --jsonl

# Generate a newsletter from summaries
python text_processor_enhanced.py summaries.jsonl --input-jsonl \
  -p "Create a newsletter highlighting the most interesting topics: {text}" \
  -o newsletter.txt
```

## How It Works

1. **File Collection**: The `FileCollector` class determines the input type and collects files accordingly:
   - For directories: Recursively finds files with specified extensions
   - For S3: Downloads files to temporary directory
   - For ZIP: Extracts matching files to temporary directory
   - For JSONL input: Combines all results into a single text file

2. **Processing**: Each file is sent to Ollama with the specified prompt template

3. **Output**: Results are formatted as JSON or JSONL based on the output flag

## Future Enhancement Ideas

1. **Parallel Processing**: Process multiple files concurrently for better performance
2. **Streaming Mode**: Support streaming responses for large files
3. **Progress Bar**: Add visual progress indicator for batch operations
4. **Resume Capability**: Save progress and resume interrupted batch jobs
5. **Filter Options**: Add filters for file size, date modified, content matching
6. **Multiple Models**: Support using different models for different file types
7. **Template Library**: Built-in prompt templates for common tasks
8. **Web UI**: Simple web interface for non-technical users
9. **Export Formats**: Support for CSV, Excel, Markdown output
10. **Caching**: Cache results to avoid reprocessing unchanged files

## Notes

- The program creates temporary directories for S3 and ZIP file processing
- JSONL chaining combines all previous results with clear separators
- File type detection is based on extensions (customizable with `-e` flag)
- Ollama must be running locally (default port: 11434)
- For large datasets, consider using `--max-records` with future versions

## Troubleshooting

- **"Cannot connect to Ollama"**: Ensure `ollama serve` is running
- **"No files found"**: Check file extensions and path patterns
- **S3 errors**: Verify AWS credentials are configured (`aws configure`)
- **Memory issues**: Process files in smaller batches or use streaming mode (future)