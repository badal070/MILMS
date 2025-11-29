"""
Multi-Stage Descriptive Answer Evaluator using Gemini API
Implements comprehensive blueprint with anti-cheat measures
"""

import os
import re
import json
import time
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai


class MultiStageAnswerEvaluator:
    """
    Advanced multi-stage evaluator implementing the full blueprint
    
    Features:
    - Gold standard answer generation
    - Automatic rubric creation
    - Independent multi-phase analysis
    - Contradiction detection
    - Fluff detection
    - Bias-balanced scoring
    """
    
    def __init__(self, api_key: str, model_name: str = None):
        """Initialize with Gemini API"""
        self.api_key = api_key
        genai.configure(api_key=api_key)
        
        if model_name is None:
            model_name = self._get_best_model()
        
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
        
        self.safety_settings = {
            'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
            'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
            'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
            'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
        }
        
        print(f"✓ Initialized Multi-Stage Evaluator with {model_name}")
    
    def _get_best_model(self) -> str:
        """Auto-detect best available Gemini model"""
        try:
            available = []
            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    available.append(model.name)
            
            preferred = [
                'models/gemini-1.5-flash-latest',
                'models/gemini-1.5-pro-latest',
                'models/gemini-pro'
            ]
            
            for model in preferred:
                if model in available:
                    return model
            
            return available[0] if available else 'gemini-pro'
        except:
            return 'gemini-pro'
    
    def evaluate_answer(
        self,
        question: str,
        user_answer: str,
        standard_answer: Optional[str] = None,
        max_score: int = 100
    ) -> Dict:
        """
        Complete multi-stage evaluation pipeline
        
        Args:
            question: The question text
            user_answer: Student's submitted answer
            standard_answer: Optional reference answer
            max_score: Maximum possible score
        
        Returns:
            Comprehensive evaluation results
        """
        print("\n" + "="*60)
        print("MULTI-STAGE EVALUATION PIPELINE")
        print("="*60)
        
        start_time = time.time()
        
        try:
            # STAGE 1: Generate/validate gold standard answer
            print("\n[Stage 1] Gold Standard Answer...")
            gold_answer = self._generate_gold_standard(question, standard_answer)
            
            # STAGE 2: Create scoring rubric
            print("[Stage 2] Generating Scoring Rubric...")
            rubric = self._generate_rubric(question, gold_answer)
            
            # STAGE 3: Analyze student answer
            print("[Stage 3] Analyzing Student Answer...")
            analysis = self._analyze_student_answer(
                question, user_answer, gold_answer, rubric
            )
            
            # STAGE 4: Check for contradictions
            print("[Stage 4] Checking Contradictions...")
            contradictions = self._check_contradictions(question, user_answer)
            
            # STAGE 5: Calculate final scores
            print("[Stage 5] Computing Final Scores...")
            final_result = self._calculate_final_scores(
                analysis, contradictions, rubric, max_score
            )
            
            # Add metadata
            execution_time = time.time() - start_time
            final_result['execution_time'] = round(execution_time, 2)
            final_result['model_used'] = self.model_name
            final_result['gold_answer'] = gold_answer
            final_result['rubric'] = rubric
            
            print(f"\n✓ Evaluation completed in {execution_time:.2f}s")
            print("="*60)
            
            return final_result
            
        except Exception as e:
            print(f"\n❌ Evaluation failed: {str(e)}")
            return self._get_fallback_result(max_score, str(e))
    
    def _generate_gold_standard(
        self, 
        question: str, 
        provided_answer: Optional[str]
    ) -> str:
        """
        STAGE 1: Generate or validate gold standard answer
        Ensures concise, factual reference (60-120 words)
        """
        if provided_answer and len(provided_answer.split()) >= 30:
            # Use provided answer if substantial
            return provided_answer.strip()
        
        prompt = f"""Generate a gold standard answer for this question. 

QUESTION: {question}

Requirements:
- Exactly 60-120 words
- Include: clear definition, inputs, outputs, core mechanism
- Be factually accurate and concise
- No fluff or filler

Return ONLY the answer text, nothing else."""

        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings
            )
            return response.text.strip()
        except Exception as e:
            return f"[Gold standard generation failed: {str(e)}]"
    
    def _generate_rubric(self, question: str, gold_answer: str) -> Dict:
        """
        STAGE 2: Extract scoring rubric from gold answer
        Creates weighted checkpoints for evaluation
        """
        prompt = f"""Analyze this gold standard answer and create a scoring rubric.

QUESTION: {question}

GOLD ANSWER:
{gold_answer}

Extract:
1. Essential points (core facts) - 40% weight
2. Supporting points (details) - 20% weight  
3. Required keywords - 20% weight
4. Structure/clarity requirements - 10% weight
5. Grammar expectations - 10% weight

Return ONLY valid JSON:
{{
    "essential_points": ["point1", "point2"],
    "supporting_points": ["detail1", "detail2"],
    "required_keywords": ["keyword1", "keyword2"],
    "weights": {{
        "essential": 0.40,
        "supporting": 0.20,
        "keywords": 0.20,
        "clarity": 0.10,
        "grammar": 0.10
    }}
}}"""

        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings
            )
            
            result = self._extract_json(response.text)
            
            # Validate structure
            if not all(k in result for k in ['essential_points', 'supporting_points', 'required_keywords']):
                raise ValueError("Invalid rubric structure")
            
            return result
            
        except Exception as e:
            print(f"  Warning: Using fallback rubric ({str(e)})")
            return {
                "essential_points": ["Core concept explanation"],
                "supporting_points": ["Additional details"],
                "required_keywords": [],
                "weights": {
                    "essential": 0.40,
                    "supporting": 0.20,
                    "keywords": 0.20,
                    "clarity": 0.10,
                    "grammar": 0.10
                }
            }
    
    def _analyze_student_answer(
        self,
        question: str,
        user_answer: str,
        gold_answer: str,
        rubric: Dict
    ) -> Dict:
        """
        STAGE 3: Comprehensive analysis of student answer
        Checks all aspects independently
        """
        essential = rubric.get('essential_points', [])
        supporting = rubric.get('supporting_points', [])
        keywords = rubric.get('required_keywords', [])
        
        prompt = f"""Analyze this student answer against the gold standard.

QUESTION: {question}

GOLD ANSWER:
{gold_answer}

STUDENT ANSWER:
{user_answer}

RUBRIC CHECKPOINTS:
Essential Points: {essential}
Supporting Points: {supporting}
Keywords: {keywords}

Evaluate:
1. Which essential points are covered? (list)
2. Which supporting points are present? (list)
3. Which keywords are used? (list)
4. What points are missing? (list)
5. Are there factual errors? (list specific errors)
6. What percentage is irrelevant fluff? (0-100)
7. Grammar quality score (0-10)
8. Clarity/structure score (0-10)
9. Relevance score (0-10)

Return ONLY valid JSON:
{{
    "covered_essential": ["point1"],
    "covered_supporting": ["detail1"],
    "keywords_found": ["keyword1"],
    "missing_points": ["point2"],
    "factual_errors": ["error description"],
    "irrelevant_segments": ["segment text"],
    "fluff_percent": 25,
    "grammar_score": 7.5,
    "clarity_score": 8.0,
    "relevance_score": 8.5
}}"""

        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings
            )
            
            result = self._extract_json(response.text)
            
            # Ensure all required fields
            defaults = {
                "covered_essential": [],
                "covered_supporting": [],
                "keywords_found": [],
                "missing_points": [],
                "factual_errors": [],
                "irrelevant_segments": [],
                "fluff_percent": 0,
                "grammar_score": 7.0,
                "clarity_score": 7.0,
                "relevance_score": 7.0
            }
            
            for key, default in defaults.items():
                result.setdefault(key, default)
            
            return result
            
        except Exception as e:
            print(f"  Warning: Analysis failed ({str(e)}), using defaults")
            return {
                "covered_essential": [],
                "covered_supporting": [],
                "keywords_found": [],
                "missing_points": ["Analysis failed"],
                "factual_errors": [],
                "irrelevant_segments": [],
                "fluff_percent": 0,
                "grammar_score": 5.0,
                "clarity_score": 5.0,
                "relevance_score": 5.0
            }
    
    def _check_contradictions(self, question: str, user_answer: str) -> List[str]:
        """
        STAGE 4: Detect factual contradictions
        Separate pass for contradiction detection
        """
        prompt = f"""Check for factual contradictions in this answer.

QUESTION: {question}

ANSWER:
{user_answer}

List any statements that contradict scientific facts or established knowledge.
Examples of contradictions:
- "Photosynthesis occurs in animals"
- "Water boils at 50°C at sea level"

Return ONLY valid JSON:
{{
    "contradictions": ["contradiction 1", "contradiction 2"]
}}"""

        try:
            response = self.model.generate_content(
                prompt,
                safety_settings=self.safety_settings
            )
            
            result = self._extract_json(response.text)
            return result.get('contradictions', [])
            
        except Exception as e:
            print(f"  Warning: Contradiction check failed ({str(e)})")
            return []
    
    def _calculate_final_scores(
        self,
        analysis: Dict,
        contradictions: List[str],
        rubric: Dict,
        max_score: int
    ) -> Dict:
        """
        STAGE 5: Calculate weighted final scores with anti-fluff measures
        """
        weights = rubric.get('weights', {
            'essential': 0.40,
            'supporting': 0.20,
            'keywords': 0.20,
            'clarity': 0.10,
            'grammar': 0.10
        })
        
        # Calculate component scores (0-10 scale)
        essential_count = len(analysis.get('covered_essential', []))
        essential_total = len(rubric.get('essential_points', [1]))
        essential_score = (essential_count / max(essential_total, 1)) * 10
        
        supporting_count = len(analysis.get('covered_supporting', []))
        supporting_total = len(rubric.get('supporting_points', [1]))
        supporting_score = (supporting_count / max(supporting_total, 1)) * 10
        
        keywords_count = len(analysis.get('keywords_found', []))
        keywords_total = len(rubric.get('required_keywords', [1]))
        keywords_score = (keywords_count / max(keywords_total, 1)) * 10
        
        clarity_score = analysis.get('clarity_score', 7.0)
        grammar_score = analysis.get('grammar_score', 7.0)
        
        # Calculate weighted average
        content_score = (
            essential_score * weights['essential'] +
            supporting_score * weights['supporting'] +
            keywords_score * weights['keywords'] +
            clarity_score * weights['clarity'] +
            grammar_score * weights['grammar']
        )
        
        # Apply penalties
        fluff_percent = analysis.get('fluff_percent', 0)
        fluff_penalty = (fluff_percent / 100) * 2  # Max 2 point penalty
        
        contradiction_penalty = len(contradictions) * 1.5  # 1.5 points per contradiction
        
        error_penalty = len(analysis.get('factual_errors', [])) * 1.0
        
        # Final adjusted score (0-10 scale)
        adjusted_score = max(0, content_score - fluff_penalty - contradiction_penalty - error_penalty)
        
        # Bias balancing: map to rating categories
        if adjusted_score >= 8.5:
            rating = "Excellent"
            score_multiplier = 1.0
        elif adjusted_score >= 7.0:
            rating = "Good"
            score_multiplier = 0.95
        elif adjusted_score >= 5.0:
            rating = "Average"
            score_multiplier = 0.85
        else:
            rating = "Poor"
            score_multiplier = 0.75
        
        # Convert to max_score scale
        final_score = (adjusted_score / 10) * max_score * score_multiplier
        final_score = max(0, min(max_score, round(final_score, 2)))
        
        percentage = round((final_score / max_score) * 100, 2)
        
        # Generate feedback
        feedback = self._generate_feedback(analysis, contradictions, rating)
        
        return {
            'overall_score': final_score,
            'max_score': max_score,
            'percentage': percentage,
            'rating': rating,
            'detailed_breakdown': {
                'essential_points_score': round(essential_score, 2),
                'supporting_points_score': round(supporting_score, 2),
                'keywords_score': round(keywords_score, 2),
                'clarity_score': round(clarity_score, 2),
                'grammar_score': round(grammar_score, 2),
                'content_score_raw': round(content_score, 2),
                'fluff_penalty': round(fluff_penalty, 2),
                'contradiction_penalty': round(contradiction_penalty, 2),
                'error_penalty': round(error_penalty, 2)
            },
            'missing_details': analysis.get('missing_points', []),
            'wrong_facts': analysis.get('factual_errors', []),
            'contradictions': contradictions,
            'strengths': self._identify_strengths(analysis),
            'fluff_percent': analysis.get('fluff_percent', 0),
            'irrelevant_segments': analysis.get('irrelevant_segments', []),
            'feedback': feedback,
            'suggested_improvement': self._generate_suggestions(analysis, contradictions)
        }
    
    def _identify_strengths(self, analysis: Dict) -> List[str]:
        """Extract strengths from analysis"""
        strengths = []
        
        if analysis.get('relevance_score', 0) >= 8:
            strengths.append("Highly relevant answer")
        
        if analysis.get('grammar_score', 0) >= 8:
            strengths.append("Good grammar and structure")
        
        if analysis.get('clarity_score', 0) >= 8:
            strengths.append("Clear explanation")
        
        if len(analysis.get('covered_essential', [])) > 0:
            strengths.append(f"Covered {len(analysis['covered_essential'])} essential points")
        
        if analysis.get('fluff_percent', 100) < 20:
            strengths.append("Concise and focused")
        
        return strengths if strengths else ["Answer submitted"]
    
    def _generate_feedback(
        self,
        analysis: Dict,
        contradictions: List[str],
        rating: str
    ) -> str:
        """Generate constructive feedback"""
        parts = [f"Rating: {rating}."]
        
        missing = analysis.get('missing_points', [])
        if missing:
            parts.append(f"Missing {len(missing)} key point(s).")
        
        errors = analysis.get('factual_errors', [])
        if errors:
            parts.append(f"Contains {len(errors)} factual error(s).")
        
        if contradictions:
            parts.append(f"Contains {len(contradictions)} contradiction(s).")
        
        fluff = analysis.get('fluff_percent', 0)
        if fluff > 30:
            parts.append(f"Reduce irrelevant content ({fluff}% fluff).")
        
        grammar = analysis.get('grammar_score', 0)
        if grammar < 6:
            parts.append("Improve grammar and sentence structure.")
        
        return " ".join(parts)
    
    def _generate_suggestions(
        self,
        analysis: Dict,
        contradictions: List[str]
    ) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []
        
        missing = analysis.get('missing_points', [])
        if missing:
            suggestions.append(f"Add coverage of: {', '.join(missing[:3])}")
        
        if contradictions:
            suggestions.append("Verify and correct factual contradictions")
        
        if analysis.get('fluff_percent', 0) > 25:
            suggestions.append("Focus on essential information, reduce filler")
        
        if analysis.get('clarity_score', 10) < 7:
            suggestions.append("Improve organization and clarity of explanation")
        
        if analysis.get('grammar_score', 10) < 7:
            suggestions.append("Review grammar and sentence construction")
        
        return suggestions if suggestions else ["Good work! Minor refinements suggested."]
    
    def _extract_json(self, text: str) -> Dict:
        """Extract and parse JSON from response"""
        # Remove markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        return json.loads(text.strip())
    
    def _get_fallback_result(self, max_score: int, error_msg: str) -> Dict:
        """Return safe fallback when evaluation fails"""
        default_score = max_score * 0.5
        
        return {
            'overall_score': default_score,
            'max_score': max_score,
            'percentage': 50.0,
            'rating': 'Average',
            'detailed_breakdown': {},
            'missing_details': ["Evaluation system error"],
            'wrong_facts': [],
            'contradictions': [],
            'strengths': [],
            'fluff_percent': 0,
            'irrelevant_segments': [],
            'feedback': f'Automatic evaluation unavailable. Manual review required.',
            'suggested_improvement': ["System error - manual grading recommended"],
            'error': error_msg
        }


# Convenience function
def evaluate_descriptive_answer(
    api_key: str,
    question: str,
    user_answer: str,
    standard_answer: Optional[str] = None,
    max_score: int = 100,
    model: str = None
) -> Dict:
    """
    Quick evaluation using multi-stage pipeline
    
    Usage:
        result = evaluate_descriptive_answer(
            api_key="your_gemini_key",
            question="Explain photosynthesis",
            user_answer="Plants make food using sunlight...",
            max_score=100
        )
        
        print(f"Score: {result['overall_score']}/{result['max_score']}")
        print(f"Rating: {result['rating']}")
        print(f"Feedback: {result['feedback']}")
    """
    evaluator = MultiStageAnswerEvaluator(api_key=api_key, model_name=model)
    return evaluator.evaluate_answer(question, user_answer, standard_answer, max_score)


# Testing
if __name__ == "__main__":
    API_KEY = os.getenv("GEMINI_API_KEY", "your-key-here")
    
    if API_KEY == "your-key-here":
        print("❌ Set GEMINI_API_KEY environment variable")
        print("Get key: https://makersuite.google.com/app/apikey")
        exit(1)
    
    # Test case
    question = "Explain the process of photosynthesis in plants."
    
    user_answer = """
    Photosynthesis is a very important process that happens in plants and it is 
    really fascinating how nature works. Plants use sunlight to make food, which 
    is amazing. The chlorophyll in leaves absorbs the sunlight and then the plant 
    takes carbon dioxide from the air. Water is also needed from the soil. Then 
    glucose is produced and oxygen is released. This process is crucial for all 
    life on Earth and without it we would not survive. Plants are truly remarkable 
    organisms that sustain life on our planet through this incredible mechanism.
    """
    
    print("\n" + "="*60)
    print("MULTI-STAGE EVALUATION TEST")
    print("="*60)
    print(f"\nQuestion: {question}")
    print(f"\nStudent Answer: {user_answer.strip()}")
    
    # Evaluate
    result = evaluate_descriptive_answer(
        api_key=API_KEY,
        question=question,
        user_answer=user_answer,
        max_score=100
    )
    
    # Display results
    print("\n" + "="*60)
    print("EVALUATION RESULTS")
    print("="*60)
    print(f"\n✓ Score: {result['overall_score']}/{result['max_score']} ({result['percentage']}%)")
    print(f"✓ Rating: {result['rating']}")
    print(f"\n📝 Feedback: {result['feedback']}")
    
    if result.get('detailed_breakdown'):
        print("\n--- Score Breakdown ---")
        for key, value in result['detailed_breakdown'].items():
            print(f"{key}: {value}")
    
    if result.get('missing_details'):
        print(f"\n📌 Missing: {result['missing_details']}")
    
    if result.get('contradictions'):
        print(f"\n⚠ Contradictions: {result['contradictions']}")
    
    if result.get('strengths'):
        print(f"\n💪 Strengths: {result['strengths']}")
    
    print(f"\n🗑 Fluff: {result.get('fluff_percent', 0)}%")
    
    if result.get('suggested_improvement'):
        print(f"\n💡 Suggestions:")
        for suggestion in result['suggested_improvement']:
            print(f"   • {suggestion}")
    
    print(f"\n⏱ Time: {result.get('execution_time', 'N/A')}s")
    print(f"🤖 Model: {result.get('model_used', 'N/A')}")
    
    print("\n" + "="*60)