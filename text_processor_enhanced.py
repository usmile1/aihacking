#!/usr/bin/env python3

import os
import sys
import argparse
import json
import zipfile
import tempfile
import glob
from pathlib import Path
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import boto3
from botocore.exceptions import NoCredentialsError, ClientError


class OllamaTextProcessor:
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.api_generate = f"{base_url}/api/generate"
        
    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except:
            return False
    
    def process_text(self, text: str, prompt_template: str) -> str:
        prompt = prompt_template.replace("{text}", text)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.api_generate, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except requests.exceptions.RequestException as e:
            return f"Error: {str(e)}"
    
    def process_file(self, file_path: Path, prompt_template: str) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result = self.process_text(content, prompt_template)
            
            return {
                "file": str(file_path),
                "status": "success",
                "result": result
            }
        except Exception as e:
            return {
                "file": str(file_path),
                "status": "error",
                "error": str(e)
            }
    
    def process_files(self, file_paths: List[Path], prompt_template: str) -> List[Dict[str, Any]]:
        results = []
        for file_path in file_paths:
            print(f"Processing: {file_path}")
            result = self.process_file(file_path, prompt_template)
            results.append(result)
        return results


class FileCollector:
    def __init__(self, extensions: Optional[List[str]] = None):
        self.extensions = extensions or ['.txt', '.md', '.log', '.csv']
        self.s3_client = None
        
    def _init_s3(self):
        if not self.s3_client:
            self.s3_client = boto3.client('s3')
    
    def _is_valid_file(self, file_path: str) -> bool:
        return any(file_path.lower().endswith(ext) for ext in self.extensions)
    
    def collect_from_directory(self, directory: str, recursive: bool = True) -> List[Path]:
        files = []
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise ValueError(f"Directory not found: {directory}")
        
        pattern = "**/*" if recursive else "*"
        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and self._is_valid_file(str(file_path)):
                files.append(file_path)
        
        return sorted(files)
    
    def collect_from_zip(self, zip_path: str) -> List[Path]:
        files = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_name in zip_ref.namelist():
                    if self._is_valid_file(file_name):
                        zip_ref.extract(file_name, temp_dir)
                        files.append(Path(temp_dir) / file_name)
        except Exception as e:
            raise ValueError(f"Error reading zip file: {str(e)}")
        
        return sorted(files)
    
    def collect_from_s3(self, s3_path: str) -> List[Path]:
        self._init_s3()
        files = []
        temp_dir = tempfile.mkdtemp()
        
        # Parse S3 path
        if not s3_path.startswith('s3://'):
            raise ValueError("S3 path must start with s3://")
        
        parts = s3_path[5:].split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''
        
        try:
            # List objects in bucket
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if self._is_valid_file(key):
                            # Download file
                            local_path = Path(temp_dir) / key.split('/')[-1]
                            self.s3_client.download_file(bucket, key, str(local_path))
                            files.append(local_path)
                            print(f"Downloaded: {key}")
        
        except NoCredentialsError:
            raise ValueError("AWS credentials not found. Configure AWS CLI or set environment variables.")
        except ClientError as e:
            raise ValueError(f"S3 error: {str(e)}")
        
        return sorted(files)
    
    def collect_from_jsonl(self, jsonl_path: str) -> List[Path]:
        """Extract and combine all results from JSONL into a single text file"""
        temp_dir = tempfile.mkdtemp()
        combined_content = []
        
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        # Extract the result text
                        result = record.get('result', '')
                        file_name = record.get('file', f'record_{i}')
                        
                        # Add to combined content with file identifier
                        combined_content.append(f"=== File: {file_name} ===")
                        combined_content.append(result)
                        combined_content.append("")  # Empty line separator
            
            # Create a single temp file with all combined results
            combined_file = Path(temp_dir) / "combined_results.txt"
            combined_file.write_text("\n".join(combined_content), encoding='utf-8')
            
            return [combined_file]
        except Exception as e:
            raise ValueError(f"Error reading JSONL file: {str(e)}")
    
    def collect_files(self, source: str, recursive: bool = True, is_jsonl_input: bool = False) -> List[Path]:
        # Check if explicitly marked as JSONL input
        if is_jsonl_input:
            if os.path.isfile(source) and source.endswith('.jsonl'):
                return self.collect_from_jsonl(source)
            else:
                raise ValueError(f"Invalid JSONL input file: {source}")
        
        # Determine source type
        if source.startswith('s3://'):
            return self.collect_from_s3(source)
        elif source.endswith('.zip'):
            return self.collect_from_zip(source)
        elif os.path.isdir(source):
            return self.collect_from_directory(source, recursive)
        elif os.path.isfile(source):
            # Single file
            if self._is_valid_file(source):
                return [Path(source)]
            else:
                print(f"Warning: {source} is not a valid file type for processing")
                return []
        else:
            # Glob pattern or comma-separated list
            files = []
            for pattern in source.split(','):
                pattern = pattern.strip()
                matched_files = glob.glob(pattern)
                if not matched_files and not any(c in pattern for c in ['*', '?', '[']):
                    # No glob chars and no matches - might be a typo
                    print(f"Warning: No files found matching '{pattern}'")
                files.extend([Path(f) for f in matched_files if os.path.isfile(f) and self._is_valid_file(f)])
            return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Process text files using Ollama from various sources")
    parser.add_argument("source", help="Source: S3 path (s3://bucket/prefix), zip file, directory, or file pattern")
    parser.add_argument("-m", "--model", default="llama3.2", help="Ollama model to use (default: llama3.2)")
    parser.add_argument("-p", "--prompt", help="Custom prompt template (use {text} as placeholder)")
    parser.add_argument("-o", "--output", help="Output file for results (JSON format)")
    parser.add_argument("--jsonl", action="store_true", help="Output in JSONL format (one result per line)")
    parser.add_argument("--input-jsonl", action="store_true", help="Input is a JSONL file from previous processing")
    parser.add_argument("--summarize", action="store_true", help="Summarize the text")
    parser.add_argument("--analyze", action="store_true", help="Analyze the text")
    parser.add_argument("--extract", action="store_true", help="Extract key information")
    parser.add_argument("-e", "--extensions", nargs="+", help="File extensions to process (default: .txt .md .log .csv)")
    parser.add_argument("--no-recursive", action="store_true", help="Don't recursively search directories")
    
    args = parser.parse_args()
    
    # Default prompts for common operations
    if args.summarize:
        prompt_template = "Please summarize the following text in 2-3 sentences:\n\n{text}"
    elif args.analyze:
        prompt_template = "Please analyze the following text and identify the main topics, tone, and key points:\n\n{text}"
    elif args.extract:
        prompt_template = "Extract the key information, facts, and important details from the following text:\n\n{text}"
    elif args.prompt:
        prompt_template = args.prompt
    else:
        prompt_template = "Process the following text and provide insights:\n\n{text}"
    
    # Initialize processor
    processor = OllamaTextProcessor(model=args.model)
    
    # Check if Ollama is running
    if not processor.check_connection():
        print("Error: Cannot connect to Ollama. Make sure it's installed and running.")
        print("Start Ollama with: ollama serve")
        sys.exit(1)
    
    # Collect files
    collector = FileCollector(extensions=args.extensions)
    try:
        print(f"Collecting files from: {args.source}")
        file_paths = collector.collect_files(args.source, recursive=not args.no_recursive, is_jsonl_input=args.input_jsonl)
        print(f"Found {len(file_paths)} files to process")
        
        if not file_paths:
            print("No valid files found to process")
            sys.exit(0)
    except Exception as e:
        print(f"Error collecting files: {str(e)}")
        sys.exit(1)
    
    # Process files
    results = processor.process_files(file_paths, prompt_template)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            if args.jsonl:
                # JSONL format: one JSON object per line
                for result in results:
                    # Extract just filename and result for cleaner output
                    jsonl_record = {
                        "file": os.path.basename(result['file']),
                        "result": result['result'] if result['status'] == 'success' else f"Error: {result.get('error', 'Unknown error')}"
                    }
                    f.write(json.dumps(jsonl_record, ensure_ascii=False) + '\n')
            else:
                # Standard JSON format
                json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    else:
        print("\n--- Results ---")
        for result in results:
            print(f"\nFile: {result['file']}")
            print(f"Status: {result['status']}")
            if result['status'] == 'success':
                print(f"Result:\n{result['result']}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
            print("-" * 50)


if __name__ == "__main__":
    main()