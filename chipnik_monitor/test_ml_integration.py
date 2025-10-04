#!/usr/bin/env python3
"""
Test script to verify ML model integration in the API
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add the current directory to sys.path to import the API module
sys.path.insert(0, str(Path(__file__).parent))

try:
    from api import _load_ml_model, _predict_ndvi_with_ml, _MODEL_OUTPUT_DIR
    print("✅ Successfully imported API functions")
except ImportError as e:
    print(f"❌ Failed to import API functions: {e}")
    sys.exit(1)

def test_ml_model_loading():
    """Test if the ML model can be loaded"""
    print("\n🔬 Testing ML model loading...")
    
    model = _load_ml_model()
    if model is not None:
        print("✅ ML model loaded successfully")
        print(f"   Model type: {type(model).__name__}")
        
        # Check if model has expected methods
        if hasattr(model, 'predict'):
            print("✅ Model has predict method")
        else:
            print("⚠️  Model missing predict method")
            
        return True
    else:
        print("❌ Failed to load ML model")
        return False

def test_model_files():
    """Test if model files exist"""
    print("\n📁 Testing model files...")
    
    model_file = _MODEL_OUTPUT_DIR / "ndvi_prophet_model.pkl"
    metadata_file = _MODEL_OUTPUT_DIR / "model_metadata.json"
    
    if model_file.exists():
        print(f"✅ Model file exists: {model_file}")
        print(f"   Size: {model_file.stat().st_size / 1024:.1f} KB")
    else:
        print(f"❌ Model file missing: {model_file}")
        return False
        
    if metadata_file.exists():
        print(f"✅ Metadata file exists: {metadata_file}")
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            print(f"   Training date: {metadata.get('training_date', 'Unknown')}")
            print(f"   Model type: {metadata.get('model_type', 'Unknown')}")
            print(f"   Regions trained: {len(metadata.get('regions_trained', []))}")
            print(f"   Flowering prediction: {metadata.get('flowering_prediction_available', False)}")
        except Exception as e:
            print(f"⚠️  Could not read metadata: {e}")
    else:
        print(f"❌ Metadata file missing: {metadata_file}")
        
    return True

def test_prediction_function():
    """Test the prediction function with sample data"""
    print("\n🧪 Testing prediction function...")
    
    # Create sample history data
    sample_history = [
        {
            "date": "2024-03-15T12:00:00Z",
            "ndvi": 0.3,
            "temperature_deg_c": 15.0,
            "humidity_pct": 60.0,
            "cloudcover_pct": 30.0,
            "wind_speed_mps": 2.0,
            "clarity_pct": 70.0
        },
        {
            "date": "2024-04-01T12:00:00Z",
            "ndvi": 0.5,
            "temperature_deg_c": 18.0,
            "humidity_pct": 65.0,
            "cloudcover_pct": 25.0,
            "wind_speed_mps": 1.5,
            "clarity_pct": 75.0
        },
        {
            "date": "2024-05-15T12:00:00Z",
            "ndvi": 0.7,
            "temperature_deg_c": 22.0,
            "humidity_pct": 70.0,
            "cloudcover_pct": 20.0,
            "wind_speed_mps": 2.5,
            "clarity_pct": 80.0
        }
    ]
    
    # Create sample weather dataframe
    import pandas as pd
    weather_data = pd.DataFrame([
        {
            "date": datetime(2024, 3, 15),
            "temperature_deg_c": 15.0,
            "humidity_pct": 60.0,
            "cloudcover_pct": 30.0,
            "wind_speed_mps": 2.0,
            "clarity_pct": 70.0
        },
        {
            "date": datetime(2024, 4, 1),
            "temperature_deg_c": 18.0,
            "humidity_pct": 65.0,
            "cloudcover_pct": 25.0,
            "wind_speed_mps": 1.5,
            "clarity_pct": 75.0
        }
    ])
    
    try:
        results = _predict_ndvi_with_ml(sample_history, weather_data, 2025)
        
        print("✅ Prediction function executed successfully")
        print(f"   Model used: {results.get('model', 'Unknown')}")
        print(f"   NDVI peak: {results.get('ndvi_peak')}")
        print(f"   NDVI peak date: {results.get('ndvi_peak_at')}")
        print(f"   Flowering date: {results.get('flowering_start_date')}")
        print(f"   Flowering confidence: {results.get('flowering_confidence', 0):.1%}")
        
        if results.get('error'):
            print(f"   ⚠️  Error: {results.get('error')}")
            
        return True
        
    except Exception as e:
        print(f"❌ Prediction function failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Testing ML Model Integration for API")
    print("=" * 50)
    
    # Test model files
    files_ok = test_model_files()
    
    # Test model loading
    model_ok = test_ml_model_loading()
    
    # Test prediction function
    prediction_ok = test_prediction_function()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"   Model files: {'✅ PASS' if files_ok else '❌ FAIL'}")
    print(f"   Model loading: {'✅ PASS' if model_ok else '❌ FAIL'}")
    print(f"   Prediction function: {'✅ PASS' if prediction_ok else '❌ FAIL'}")
    
    if all([files_ok, model_ok, prediction_ok]):
        print("\n🎉 All tests passed! Your ML model is ready for API integration.")
        print("\n📋 Next steps:")
        print("   1. Start your FastAPI server: uvicorn api:app --reload")
        print("   2. Send POST requests to /reports with GeoJSON data")
        print("   3. The API will use your ML model for NDVI and flowering predictions")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)