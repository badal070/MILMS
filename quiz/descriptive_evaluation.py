"""
Answer Evaluator Utils - Free Tier Version
A comprehensive utility for evaluating descriptive answers using free AI APIs
Uses Hugging Face Inference API (Free Tier)
"""

import os
import re
import json
import requests
from typing import Dict, List, Optional, Tuple
import time


class AnswerEvaluator:
    """
    AI-powered evaluator for descriptive answers using free Hugging Face API
    """
    
    def __init__(self, api_key: str, model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"):
        """
        Initialize the evaluator with API credentials
        
        Args:
            api_key: Hugging Face API key (free tier available at huggingface.co)
            model: Model to use - options:
                - "mistralai/Mixtral-8x7B-Instruct-v0.1" (recommended, powerful)
                - "meta-llama/Llama-2-7b-chat-hf"
                - "microsoft/Phi-3-mini-4k-instruct"
        """
        self.api_key = api_key
        self.model = model
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def _call_api(self, prompt: str, max_retries: int = 3) -> str:
        """Call Hugging Face API with retry logic"""
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.3,
                "top_p": 0.9,
                "return_full_text": False
            }
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url, 
                    headers=self.headers, 
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 503:
                    # Model is loading, wait and retry
                    wait_time = 10 * (attempt + 1)
                    print(f"Model loading, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    return result.get("generated_text", "")
                
                return str(result)
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    return f"API Error: {str(e)}"
                time.sleep(2)
        
        return "API Error: Max retries reached"
    
    def evaluate_answer(
        self, 
        question: str, 
        user_answer: str, 
        standard_answer: Optional[str] = None,
        max_score: int = 100
    ) -> Dict:
        """
        Comprehensive evaluation of a descriptive answer
        
        Args:
            question: The question asked
            user_answer: The user's submitted answer
            standard_answer: Optional reference answer for comparison
            max_score: Maximum score possible (default: 100)
            
        Returns:
            Dictionary containing detailed evaluation results
        """
        
        # Stage 1: Spell check on keywords
        print("Checking spelling...")
        spelling_result = self._check_spelling(question, user_answer)
        
        # Stage 2: Relevance check
        print("Checking relevance...")
        relevance_result = self._check_relevance(question, user_answer)
        
        # Stage 3: Content quality and completeness
        print("Analyzing content quality...")
        content_result = self._check_content_quality(
            question, user_answer, standard_answer
        )
        
        # Stage 4: Grammar check
        print("Checking grammar...")
        grammar_result = self._check_grammar(user_answer)
        
        # Calculate final score
        final_score = self._calculate_score(
            spelling_result,
            relevance_result,
            content_result,
            grammar_result,
            max_score
        )
        
        return {
            "overall_score": final_score,
            "max_score": max_score,
            "percentage": round((final_score / max_score) * 100, 2),
            "spelling_analysis": spelling_result,
            "relevance_analysis": relevance_result,
            "content_analysis": content_result,
            "grammar_analysis": grammar_result,
            "feedback": self._generate_feedback(
                spelling_result,
                relevance_result,
                content_result,
                grammar_result
            )
        }
    
    def _check_spelling(self, question: str, answer: str) -> Dict:
        """Check spelling mistakes in major keywords"""
        
        prompt = f"""[INST] You are an expert evaluator. Analyze the spelling in this answer.

Question: {question}
Answer: {answer}

Provide your analysis in this exact JSON format (no other text):
{{
    "keywords_checked": ["keyword1", "keyword2"],
    "spelling_errors": [{{"word": "misspelled", "correction": "correct", "severity": "high"}}],
    "spelling_score": 8.5,
    "notes": "Brief assessment"
}}
[/INST]"""
        
        try:
            response = self._call_api(prompt)
            result = self._extract_json(response)
            
            # Ensure score exists
            if "spelling_score" not in result:
                result["spelling_score"] = self._estimate_spelling_score(answer)
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "spelling_score": 7.0,
                "keywords_checked": [],
                "spelling_errors": [],
                "notes": "Error during spelling check"
            }
    
    def _check_relevance(self, question: str, answer: str) -> Dict:
        """Check if answer is relevant to the question"""
        
        prompt = f"""[INST] You are an expert evaluator. Check if this answer is relevant to the question.

Question: {question}
Answer: {answer}

Provide your analysis in this exact JSON format (no other text):
{{
    "is_relevant": true,
    "relevance_score": 8.5,
    "addresses_question": true,
    "off_topic_content": [],
    "notes": "Brief explanation"
}}
[/INST]"""
        
        try:
            response = self._call_api(prompt)
            result = self._extract_json(response)
            
            if "relevance_score" not in result:
                result["relevance_score"] = 7.0
            if "is_relevant" not in result:
                result["is_relevant"] = True
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "relevance_score": 7.0,
                "is_relevant": True,
                "addresses_question": True,
                "notes": "Error during relevance check"
            }
    
    def _check_content_quality(
        self, 
        question: str, 
        answer: str, 
        standard_answer: Optional[str]
    ) -> Dict:
        """Check content quality and completeness"""
        
        standard_text = f"\n\nReference Answer:\n{standard_answer}" if standard_answer else ""
        
        prompt = f"""[INST] You are an expert evaluator. Assess the quality and completeness of this answer.

Question: {question}
User's Answer: {answer}{standard_text}

Provide your analysis in this exact JSON format (no other text):
{{
    "content_score": 8.5,
    "elegance_score": 7.5,
    "completeness_score": 8.0,
    "missing_details": ["detail1", "detail2"],
    "strengths": ["strength1"],
    "weaknesses": ["weakness1"],
    "notes": "Overall assessment"
}}
[/INST]"""
        
        try:
            response = self._call_api(prompt)
            result = self._extract_json(response)
            
            if "content_score" not in result:
                result["content_score"] = 7.0
            if "elegance_score" not in result:
                result["elegance_score"] = 7.0
            if "completeness_score" not in result:
                result["completeness_score"] = 7.0
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "content_score": 7.0,
                "elegance_score": 7.0,
                "completeness_score": 7.0,
                "missing_details": [],
                "strengths": [],
                "weaknesses": [],
                "notes": "Error during content analysis"
            }
    
    def _check_grammar(self, answer: str) -> Dict:
        """Check grammar and language quality"""
        
        prompt = f"""[INST] You are an expert evaluator. Analyze the grammar in this text.

Text: {answer}

Provide your analysis in this exact JSON format (no other text):
{{
    "grammar_score": 8.5,
    "grammar_errors": [{{"error": "description", "correction": "fix"}}],
    "sentence_structure_score": 8.0,
    "clarity_score": 9.0,
    "notes": "Brief assessment"
}}
[/INST]"""
        
        try:
            response = self._call_api(prompt)
            result = self._extract_json(response)
            
            if "grammar_score" not in result:
                result["grammar_score"] = 7.0
            if "sentence_structure_score" not in result:
                result["sentence_structure_score"] = 7.0
            if "clarity_score" not in result:
                result["clarity_score"] = 7.0
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "grammar_score": 7.0,
                "grammar_errors": [],
                "sentence_structure_score": 7.0,
                "clarity_score": 7.0,
                "notes": "Error during grammar check"
            }
    
    def _estimate_spelling_score(self, text: str) -> float:
        """Simple heuristic for spelling if API fails"""
        # Basic check for common patterns
        words = text.split()
        if len(words) < 10:
            return 8.0
        return 7.5
    
    def _calculate_score(
        self,
        spelling: Dict,
        relevance: Dict,
        content: Dict,
        grammar: Dict,
        max_score: int
    ) -> float:
        """Calculate weighted final score"""
        
        weights = {
            "spelling": 0.15,
            "relevance": 0.30,
            "content": 0.40,
            "grammar": 0.15
        }
        
        spelling_score = spelling.get("spelling_score", 7.0)
        relevance_score = relevance.get("relevance_score", 7.0)
        content_score = content.get("content_score", 7.0)
        grammar_score = grammar.get("grammar_score", 7.0)
        
        weighted_avg = (
            spelling_score * weights["spelling"] +
            relevance_score * weights["relevance"] +
            content_score * weights["content"] +
            grammar_score * weights["grammar"]
        )
        
        final_score = (weighted_avg / 10) * max_score
        
        return round(final_score, 2)
    
    def _generate_feedback(
        self,
        spelling: Dict,
        relevance: Dict,
        content: Dict,
        grammar: Dict
    ) -> str:
        """Generate human-readable feedback"""
        
        feedback_parts = []
        
        # Spelling feedback
        spelling_errors = spelling.get("spelling_errors", [])
        if spelling_errors:
            error_words = [e.get('word', '') for e in spelling_errors[:3]]
            feedback_parts.append(
                f"Spelling: Found {len(spelling_errors)} error(s). "
                f"Review: {', '.join(error_words)}"
            )
        else:
            feedback_parts.append("Spelling: Good, no major errors.")
        
        # Relevance feedback
        rel_score = relevance.get("relevance_score", 7.0)
        if rel_score < 5:
            feedback_parts.append("Relevance: Answer is off-topic. Please address the question directly.")
        elif rel_score < 7:
            feedback_parts.append("Relevance: Answer partially addresses the question.")
        else:
            feedback_parts.append("Relevance: Well-focused and on-topic.")
        
        # Content feedback
        missing = content.get("missing_details", [])
        if missing:
            feedback_parts.append(f"Content: Add details on: {', '.join(missing[:2])}")
        
        strengths = content.get("strengths", [])
        if strengths:
            feedback_parts.append(f"Strengths: {', '.join(strengths[:2])}")
        
        # Grammar feedback
        grammar_errors = grammar.get("grammar_errors", [])
        if len(grammar_errors) > 3:
            feedback_parts.append(f"Grammar: {len(grammar_errors)} errors detected. Review carefully.")
        elif grammar_errors:
            feedback_parts.append("Grammar: Minor improvements needed.")
        else:
            feedback_parts.append("Grammar: Well-written.")
        
        return " | ".join(feedback_parts)
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from AI response"""
        try:
            # Remove markdown code blocks
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            # Find JSON object
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            
            # Try parsing entire text
            return json.loads(text)
            
        except (json.JSONDecodeError, AttributeError):
            # Return default structure if parsing fails
            return {
                "notes": "Could not parse response",
                "error": "JSON parse error"
            }


# Convenience function
def evaluate_descriptive_answer(
    api_key: str,
    question: str,
    user_answer: str,
    standard_answer: Optional[str] = None,
    max_score: int = 100,
    model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"
) -> Dict:
    """
    Quick function to evaluate a descriptive answer using free Hugging Face API
    
    Setup:
        1. Get free API key from https://huggingface.co/settings/tokens
        2. No credit card required!
    
    Usage:
        result = evaluate_descriptive_answer(
            api_key="hf_xxxxx",
            question="What is photosynthesis?",
            user_answer="Photosynthesis is when plants make food...",
            standard_answer="Photosynthesis is the process...",
            max_score=100
        )
        
        print(f"Score: {result['overall_score']}/{result['max_score']}")
        print(f"Feedback: {result['feedback']}")
    """
    evaluator = AnswerEvaluator(api_key=api_key, model=model)
    return evaluator.evaluate_answer(question, user_answer, standard_answer, max_score)


# Example usage
if __name__ == "__main__":
    # Get API key from environment or use directly
    API_KEY = os.getenv("HUGGINGFACE_API_KEY", "your-hf-api-key-here")
    
    question = "Explain the process of photosynthesis in plants."
    
    user_answer = """
    Photosynthesis is the proces by which plants make there food. 
    It happens in the leaves where clorophyll absorbs sunlight. 
    The plant takes carbon dioxide from air and water from soil.
    Then it makes glucose and releases oxigen. This is important for life on earth.
    """
    
    standard_answer = """
    Photosynthesis is the biochemical process by which plants convert light energy 
    into chemical energy. It occurs primarily in the chloroplasts of leaf cells, 
    where chlorophyll pigments absorb sunlight. During photosynthesis, plants take 
    in carbon dioxide from the atmosphere and water from the soil. Through a series 
    of light-dependent and light-independent reactions, these raw materials are 
    converted into glucose (a simple sugar) and oxygen. The glucose serves as an 
    energy source for the plant, while oxygen is released as a byproduct.
    """
    
    print("Starting evaluation with Hugging Face Free API...")
    print("=" * 60)
    
    evaluator = AnswerEvaluator(api_key=API_KEY)
    result = evaluator.evaluate_answer(
        question=question,
        user_answer=user_answer,
        standard_answer=standard_answer,
        max_score=100
    )
    
    print("\n" + "=" * 60)
    print("ANSWER EVALUATION RESULTS")
    print("=" * 60)
    print(f"\nOverall Score: {result['overall_score']}/{result['max_score']} ({result['percentage']}%)")
    print(f"\nFeedback:\n{result['feedback']}")
    print("\n--- Detailed Scores ---")
    print(f"Spelling: {result['spelling_analysis'].get('spelling_score', 'N/A')}/10")
    print(f"Relevance: {result['relevance_analysis'].get('relevance_score', 'N/A')}/10")
    print(f"Content: {result['content_analysis'].get('content_score', 'N/A')}/10")
    print(f"Grammar: {result['grammar_analysis'].get('grammar_score', 'N/A')}/10")