#!/usr/bin/env python3
"""
Simple test script for the memory optimization and profiling modules.
This tests the functionality without requiring API calls.
"""

import os
import sys
import json
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import our optimization and profiling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from kometa_ai.utils.profiling import profiler, profile_time
    from kometa_ai.utils.memory_optimization import (
        optimize_movie_objects, process_in_chunks, clear_memory
    )
    modules_loaded = True
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    modules_loaded = False

def load_test_data(file_path):
    """Load test data from JSON file."""
    logger.info(f"Loading test data from {file_path}")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} items from {file_path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        return []

@profile_time
def test_memory_optimization(data):
    """Test memory optimization functions."""
    logger.info(f"Testing memory optimization with {len(data)} items")
    
    # Start profiling
    profiler.start()
    
    # Test optimizing movie objects
    optimized_data = optimize_movie_objects(data)
    logger.info(f"Optimized {len(optimized_data)} movie objects")
    
    # Test processing in chunks
    def process_chunk(chunk):
        # Simple processing function that does something with each item
        result = []
        for item in chunk:
            # Just a simple transformation
            result.append({
                'id': item.get('id', 0),
                'processed': True
            })
        return result
    
    # Process data in chunks of 10
    chunk_results = process_in_chunks(data, 10, process_chunk)
    logger.info(f"Processed {len(data)} items in {len(chunk_results)} chunks")
    
    # Test garbage collection
    clear_memory()
    logger.info("Cleared memory")
    
    # Stop profiling and get results
    profiling_results = profiler.stop()
    logger.info("Profiling completed")
    
    return profiling_results

def main():
    """Main test function."""
    if not modules_loaded:
        logger.error("Required modules not loaded. Exiting.")
        return 1
    
    # Check command line arguments
    if len(sys.argv) < 2:
        logger.error("Usage: python test_optimization.py <test_data_file>")
        return 1
    
    test_data_file = sys.argv[1]
    if not os.path.exists(test_data_file):
        logger.error(f"Test data file not found: {test_data_file}")
        return 1
    
    # Load test data
    data = load_test_data(test_data_file)
    if not data:
        logger.error("No test data loaded. Exiting.")
        return 1
    
    # Run memory optimization tests
    results = test_memory_optimization(data)
    
    # Save results
    results_file = f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {results_file}")
    except Exception as e:
        logger.error(f"Failed to save results: {e}")
    
    logger.info("Tests completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())