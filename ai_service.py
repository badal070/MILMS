"""
AI Evaluation Service for Descriptive Quiz System
================================================

This module provides AI-powered evaluation for descriptive quiz answers
using Google's Gemini API.

Dependencies:
    pip install google-generativeai python-dotenv

Environment Variables:
    GEMINI_API_KEY: Your Google Gemini API key

Integration Points:
    - Called from: views.py -> take_descriptive_quiz() 
    - Used with: descriptive_validator.py for pre-evaluation validation
    - Stores results in: DescriptiveAnswer model fields
"""

import os
import json
import google.generativeai as genai
from typing import Dict, Optional


class AIEvaluationService:
    """
    Handles AI-powered evaluation of descriptive quiz answers using Gemini.
    
    Features:
    - Multi-dimensional scoring (content, relevance, grammar, spelling)
    - Detailed feedback generation
    - Configurable scoring parameters
    - Error handling and fallback mechanisms
    """
    
    SUPPORTED_MODELS = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    DEFAULT_MODEL = "gemini-1.5-flash"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI evaluation service.
        
        Args:
            api_key: Google Gemini API key. If None, reads from environment.
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set it in environment or pass to constructor."
            )
        
        genai.configure(api_key=self.api_key)
        self.model = None
    
    def _get_model(self, model_name: str):
        """Get or create model instance."""
        if model_name not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model: {model_name}. "
                f"Supported models: {', '.join(self.SUPPORTED_MODELS)}"
            )
        
        return genai.GenerativeModel(model_name)
    
    def _create_evaluation_prompt(
        self,
        question: str,
        user_answer: str,
        reference_answer: str,
        max_score: float
    ) -> str:
        """
        Create the evaluation prompt for the AI model.
        
        Args:
            question: The quiz question text
            user_answer: Student's submitted answer
            reference_answer: Model/reference answer for comparison
            max_score: Maximum marks for this question
        
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are an expert teacher evaluating a student's answer to a descriptive question.

QUESTION:
{question}

REFERENCE ANSWER:
{reference_answer}

STUDENT'S ANSWER:
{user_answer}

EVALUATION CRITERIA:
Evaluate the student's answer on the following dimensions (each out of {max_score} marks):

1. CONTENT ACCURACY ({max_score} marks):
   - Correctness of facts and concepts
   - Depth of understanding
   - Coverage of key points

2. RELEVANCE ({max_score} marks):
   - Directly addresses the question
   - Stays on topic
   - No irrelevant information

3. GRAMMAR & STRUCTURE ({max_score} marks):
   - Proper sentence structure
   - Correct grammar usage
   - Logical flow and organization

4. SPELLING & LANGUAGE ({max_score} marks):
   - Correct spelling
   - Appropriate vocabulary
   - Clear expression

INSTRUCTIONS:
1. Evaluate each dimension carefully
2. Compare with the reference answer but don't penalize different valid approaches
3. Be fair and constructive
4. Provide specific feedback

OUTPUT FORMAT (JSON):
{{
    "detailed_breakdown": {{
        "content_score": <float 0-{max_score}>,
        "relevance_score": <float 0-{max_score}>,
        "grammar_score": <float 0-{max_score}>,
        "spelling_score": <float 0-{max_score}>
    }},
    "overall_score": <float 0-{max_score}>,
    "strengths": ["strength1", "strength2"],
    "improvements": ["improvement1", "improvement2"],
    "feedback": "<detailed constructive feedback>"
}}

Respond ONLY with valid JSON, no additional text."""
        
        return prompt
    
    def evaluate_answer(
        self,
        question: str,
        user_answer: str,
        reference_answer: str,
        max_score: float = 10.0,
        model_name: str = None
    ) -> Dict:
        """
        Evaluate a student's descriptive answer using AI.
        
        Args:
            question: The quiz question text
            user_answer: Student's submitted answer
            reference_answer: Model/reference answer for comparison
            max_score: Maximum marks for this question (default: 10.0)
            model_name: Gemini model to use (default: gemini-1.5-flash)
        
        Returns:
            Dictionary containing:
                - detailed_breakdown: Scores for each dimension
                - overall_score: Total score
                - strengths: List of strengths
                - improvements: List of areas for improvement
                - feedback: Detailed feedback text
                - success: Boolean indicating success
                - error: Error message if failed
        
        Example:
            >>> service = AIEvaluationService()
            >>> result = service.evaluate_answer(
            ...     question="Explain photosynthesis",
            ...     user_answer="Plants make food using sunlight...",
            ...     reference_answer="Photosynthesis is the process...",
            ...     max_score=10.0
            ... )
            >>> print(result['overall_score'])
            8.5
        """
        model_name = model_name or self.DEFAULT_MODEL
        
        try:
            # Get model
            model = self._get_model(model_name)
            
            # Create prompt
            prompt = self._create_evaluation_prompt(
                question=question,
                user_answer=user_answer,
                reference_answer=reference_answer,
                max_score=max_score
            )
            
            # Generate evaluation
            response = model.generate_content(prompt)
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Validate and sanitize scores
            result = self._validate_scores(result, max_score)
            
            # Add success flag
            result['success'] = True
            result['error'] = None
            
            return result
            
        except json.JSONDecodeError as e:
            return self._create_error_response(
                f"Failed to parse AI response: {str(e)}",
                max_score
            )
        
        except Exception as e:
            return self._create_error_response(
                f"AI evaluation failed: {str(e)}",
                max_score
            )
    
    def _validate_scores(self, result: Dict, max_score: float) -> Dict:
        """
        Validate and clamp scores to valid ranges.
        
        Args:
            result: Raw result from AI
            max_score: Maximum allowed score
        
        Returns:
            Validated result dictionary
        """
        # Ensure detailed_breakdown exists
        if 'detailed_breakdown' not in result:
            result['detailed_breakdown'] = {}
        
        breakdown = result['detailed_breakdown']
        
        # Clamp individual scores
        for key in ['content_score', 'relevance_score', 'grammar_score', 'spelling_score']:
            if key not in breakdown:
                breakdown[key] = 0.0
            else:
                breakdown[key] = max(0.0, min(float(breakdown[key]), max_score))
        
        # Calculate overall score if missing
        if 'overall_score' not in result:
            result['overall_score'] = sum(breakdown.values()) / 4.0
        else:
            result['overall_score'] = max(0.0, min(float(result['overall_score']), max_score))
        
        # Ensure required fields exist
        if 'strengths' not in result:
            result['strengths'] = []
        if 'improvements' not in result:
            result['improvements'] = []
        if 'feedback' not in result:
            result['feedback'] = "Evaluation completed."
        
        return result
    
    def _create_error_response(self, error_message: str, max_score: float) -> Dict:
        """
        Create a standardized error response.
        
        Args:
            error_message: Error description
            max_score: Maximum score for the question
        
        Returns:
            Error response dictionary
        """
        return {
            'detailed_breakdown': {
                'content_score': 0.0,
                'relevance_score': 0.0,
                'grammar_score': 0.0,
                'spelling_score': 0.0
            },
            'overall_score': 0.0,
            'strengths': [],
            'improvements': [],
            'feedback': f"Automatic evaluation unavailable. {error_message}",
            'success': False,
            'error': error_message
        }
    
    def batch_evaluate(
        self,
        evaluations: list,
        model_name: str = None
    ) -> list:
        """
        Evaluate multiple answers in batch.
        
        Args:
            evaluations: List of dicts with keys: question, user_answer, 
                        reference_answer, max_score
            model_name: Gemini model to use
        
        Returns:
            List of evaluation results
        
        Example:
            >>> service = AIEvaluationService()
            >>> results = service.batch_evaluate([
            ...     {
            ...         'question': 'What is AI?',
            ...         'user_answer': 'AI is...',
            ...         'reference_answer': 'Artificial Intelligence...',
            ...         'max_score': 10.0
            ...     },
            ...     # ... more evaluations
            ... ])
        """
        results = []
        
        for eval_data in evaluations:
            result = self.evaluate_answer(
                question=eval_data['question'],
                user_answer=eval_data['user_answer'],
                reference_answer=eval_data['reference_answer'],
                max_score=eval_data.get('max_score', 10.0),
                model_name=model_name
            )
            results.append(result)
        
        return results


# Convenience function for backward compatibility
def evaluate_descriptive_answer(
    api_key: str,
    question: str,
    user_answer: str,
    standard_answer: str,
    max_score: float = 10.0,
    model: str = "gemini-1.5-flash"
) -> Dict:
    """
    Legacy function for evaluating descriptive answers.
    
    Args:
        api_key: Gemini API key
        question: Question text
        user_answer: Student's answer
        standard_answer: Reference answer
        max_score: Maximum marks
        model: Model name to use
    
    Returns:
        Evaluation result dictionary
    """
    service = AIEvaluationService(api_key=api_key)
    return service.evaluate_answer(
        question=question,
        user_answer=user_answer,
        reference_answer=standard_answer,
        max_score=max_score,
        model_name=model
    )


# Example usage
if __name__ == "__main__":
    # Initialize service
    service = AIEvaluationService()
    
    # Example evaluation
    result = service.evaluate_answer(
        question="Explain the process of photosynthesis.",
        user_answer="Photosynthesis is how plants make food using sunlight, water, and carbon dioxide.",
        reference_answer="Photosynthesis is the process by which plants convert light energy into chemical energy, using chlorophyll to capture sunlight and combine water and carbon dioxide to produce glucose and oxygen.",
        max_score=10.0
    )
    
    print("Evaluation Result:")
    print(f"Overall Score: {result['overall_score']}/{result.get('max_score', 10.0)}")
    print(f"\nDetailed Breakdown:")
    for key, value in result['detailed_breakdown'].items():
        print(f"  {key}: {value}")
    print(f"\nFeedback: {result['feedback']}")