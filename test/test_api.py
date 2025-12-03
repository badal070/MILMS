import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def test_free_gemini_api():
    """Test Gemini free-tier API connectivity and functionality"""
    
    print("=" * 60)
    print("GEMINI FREE-TIER API TEST")
    print("=" * 60)
    
    

    # Check API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment variables")
        return False
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")

    # Configure API
    try:
        genai.configure(api_key=api_key)
        print("✓ API configured successfully")
    except Exception as e:
        print(f"❌ Configuration failed: {str(e)}")
        return 
    
    


    # Select a free-tier model
    available_models = [m.name for m in genai.list_models()]
    print("All models returned by the API:")
    for m in available_models:
        print(" -", m)


    # Basic text generation
    print("\n[2] Testing basic text generation...")
    try:
        model = genai.GenerativeModel(model_name = "models/gemini-flash-latest"
)
        response = model.generate_content("Say 'Hello, free-tier API is working!' in exactly those words.")
        print(f"✓ Response: {response.text}")
    except Exception as e:
        print(f"❌ Text generation failed: {str(e)}")
        return False

    # JSON test (simple)
    print("\n[3] Testing JSON generation...")
    try:
        prompt = """Return only valid JSON with structure: {"status": "success", "message": "Free-tier test OK"}"""
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1].replace('json', '').strip()
        parsed = json.loads(result_text)
        print(f"✓ JSON parsed successfully: {parsed}")
    except Exception as e:
        print(f"❌ JSON test failed: {str(e)}")
        return False

    print("\n✅ FREE-TIER GEMINI API TEST PASSED!")
    print(f"Recommended model for free-tier: {model.model_name}")

    return True


if __name__ == "__main__":
    print("\nGEMINI FREE-TIER API TEST SCRIPT")
    success = test_free_gemini_api()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
