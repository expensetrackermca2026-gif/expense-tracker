import os
import google.generativeai as genai
from typing import List, Dict

class AIInsightService:
    @staticmethod
    def calculate_metrics(income: float, expenses: List[Dict]):
        """
        Processes raw transactional data into high-level metrics for the UI.
        """
        total_spent = sum(exp.get('amount', 0) for exp in expenses)
        
        # Category Aggregation
        categories = {}
        for exp in expenses:
          cat = exp.get('category', 'Miscellaneous')
          categories[cat] = categories.get(cat, 0) + exp.get('amount', 0)
        
        # Identify top category & percentage split
        top_category = "N/A"
        top_amount = 0
        if categories:
          top_category = max(categories, key=categories.get)
          top_amount = categories[top_category]
        
        cat_split = []
        for cat, amt in categories.items():
            cat_split.append({
                "category": cat,
                "amount": amt,
                "percentage": round((amt / total_spent * 100), 1) if total_spent > 0 else 0
            })
        
        # Consistency Check: Sum of categories should match total spent
        category_sum = sum(categories.values())
        data_consistent = abs(total_spent - category_sum) < 0.01

        return {
            "total_spent": total_spent,
            "savings": income - total_spent,
            "top_category": {
                "name": top_category,
                "amount": top_amount,
                "percentage": round((top_amount / total_spent * 100), 1) if total_spent > 0 else 0
            },
            "category_split": cat_split,
            "is_consistent": data_consistent
        }

    @staticmethod
    async def get_ai_advice(income: float, spent: float):
        """
        Generates AI-powered financial tips using Gemini Flash.
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return AIInsightService.get_deterministic_advice(income, spent)

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            prompt = f"""
            Analyze these financials: Income ₹{income}, Spending ₹{spent}.
            Generate 2 short, impactful financial tips (max 15 words each).
            Return as a simple JSON list: ["Tip 1", "Tip 2"]
            """
            
            response = model.generate_content(prompt)
            # Simple text parsing for the list
            text = response.text.strip()
            # Clean any markdown if present
            if '```' in text:
                text = text.split('```')[1].replace('json', '').strip()
            
            return text
        except Exception as e:
            print(f"AI Insight Error: {e}")
            return AIInsightService.get_deterministic_advice(income, spent)

    @staticmethod
    def get_deterministic_advice(income: float, spent: float):
        """
        Safe fallback if AI fails or key is missing.
        """
        savings_rate = ((income - spent) / income * 100) if income > 0 else 0
        
        if savings_rate < 10:
            return ["Increase savings to at least 20% of income.", "Reduce discretionary expenses this month."]
        elif spent > income:
            return ["Warning: Spending exceeds income. Use credit sparingly.", "Review fixed costs for monthly optimization."]
        else:
            return ["Keep up the good savings rate!", "Consider investing surplus in liquid funds."]
