from descriptive_evaluation import evaluate_descriptive_answer

API_KEY = 'AIzaSyD2TWT-jx9gJKHqP1NA3zjeVw38UGPfiOY'

def pretty_print_evaluation(result: dict):
    print("\n" + "="*70)
    print(" DESCRIPTIVE ANSWER EVALUATION REPORT")
    print("="*70)

    # Safe extraction
    overall = result.get("overall_score", "N/A")
    max_score = result.get("max_score", "N/A")
    percent = result.get("percentage", "N/A")

    print(f"Overall Score : {overall}/{max_score} ({percent}%)\n")

    print("SCORES\n" + "-"*70)
    for key, value in result.items():
        if key in ["feedback", "execution_time", "model_used", "raw_response", "overall_score", "max_score", "percentage"]:
            continue

        if isinstance(value, dict):
            print(f"{key}:")
            for sub_k, sub_v in value.items():
                print(f"   • {sub_k}: {sub_v}")
        else:
            print(f"{key}: {value}")

    print("\nFEEDBACK\n" + "-"*70)
    print(result.get("feedback", "No feedback available."))

    print("\nMETA INFO\n" + "-"*70)
    print(f"Execution Time : {result.get('execution_time', 'N/A')}s")
    print(f"Model Used     : {result.get('model_used', 'N/A')}")

    print("="*70 + "\n")


# Example test run
question = "What is photosynthesis?"
user_answer = "Photosynthesis is how plants make food using sun."
standard_answer = "Photosynthesis is the process where plants convert light energy into chemical energy, producing glucose and oxygen."

result = evaluate_descriptive_answer(
    api_key=API_KEY,
    question=question,
    user_answer=user_answer,
    standard_answer=standard_answer,
    max_score=100,
    model="models/gemini-flash-latest"
)

pretty_print_evaluation(result)
