#!/usr/bin/env python3

import os
import sys
import argparse
import json
from pathlib import Path
import requests
from typing import List, Dict, Any


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


def main():
    parser = argparse.ArgumentParser(description="Process text files using Ollama")
    parser.add_argument("files", nargs="+", help="Text files to process")
    parser.add_argument("-m", "--model", default="llama3.2", help="Ollama model to use (default: llama3.2)")
    parser.add_argument("-p", "--prompt", help="Custom prompt template (use {text} as placeholder)")
    parser.add_argument("-o", "--output", help="Output file for results (JSON format)")
    parser.add_argument("--summarize", action="store_true", help="Summarize the text")
    parser.add_argument("--analyze", action="store_true", help="Analyze the text")
    parser.add_argument("--extract", action="store_true", help="Extract key information")
    
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
    
    # Process files
    file_paths = [Path(f) for f in args.files]
    results = processor.process_files(file_paths, prompt_template)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
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