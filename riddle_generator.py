from groq import Groq
import json
from riddle_history import RiddleHistory


class RiddleGenerator:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.history = RiddleHistory()
        
    def _generate_riddle_batch(self, count):
        """Generate a batch of riddles from Groq"""
        prompt = f"""Generate {count} unique, creative riddles with their answers. 
        Each riddle should be different from common, well-known riddles.
        Make them engaging but not too difficult.
        Format as JSON array of objects with 'question' and 'answer' fields.
        Return ONLY the JSON array, no extra text.
        
        Guidelines:
        - Avoid common riddles like "what has keys but no locks"
        - Make them clever but solvable
        - Keep questions concise
        - Ensure answers are clear and definitive
        """
        
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return None
            
    def generate_riddles(self, count=3, max_attempts=3):
        """Generate unique riddles that haven't been used before"""
        unique_riddles = []
        attempts = 0
        
        while len(unique_riddles) < count and attempts < max_attempts:
            batch_size = (count - len(unique_riddles)) * 2
            riddles = self._generate_riddle_batch(batch_size)
            
            if riddles:
                for riddle in riddles:
                    if not self.history.is_riddle_used(riddle):
                        unique_riddles.append(riddle)
                        if len(unique_riddles) >= count:
                            break
            
            attempts += 1
        
        if unique_riddles:
            self.history.add_riddles(unique_riddles)
            
        return unique_riddles[:count] if unique_riddles else None