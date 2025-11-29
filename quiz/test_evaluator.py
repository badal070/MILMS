from descriptive_evaluation import evaluate_descriptive_answer

API_KEY = ''
def pretty_print_evaluation(result: dict):
    print("\n" + "="*60)
    print("✅ DESCRIPTIVE ANSWER EVALUATION REPORT")
    print("="*60)
    print(f"Overall Score : {result['overall_score']}/{result['max_score']} ({result['percentage']}%)\n")
    print("Detailed Scores:")
    print(f"  Spelling  : {result['spelling_score']}/10")
    print(f"  Relevance : {result['relevance_score']}/10")
    print(f"  Content   : {result['content_score']}/10")
    print(f"  Grammar   : {result['grammar_score']}/10\n")

    if result.get('spelling_errors'):
        print(f"⚠ Spelling Errors: {', '.join(result['spelling_errors'])}")
    if result.get('missing_details'):
        print(f"📌 Missing Details: {', '.join(result['missing_details'])}")
    if result.get('strengths'):
        print(f"💪 Strengths: {', '.join(result['strengths'])}")
    
    print(f"\n📝 Feedback:\n{result.get('feedback')}\n")
    print(f"⏱ Execution Time: {result.get('execution_time', 'N/A')}s")
    print(f"🤖 Model Used: {result.get('model_used', 'N/A')}")
    print("="*60 + "\n")


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
