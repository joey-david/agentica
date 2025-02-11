import random
from datetime import datetime
from db import get_connection

def run_daily_survey():
    topic = input("What did you study today? ")
    notes = input(f"Give some details about your work on '{topic}': ")
    depth = input("On a scale of 1-5, how technical and advanced was your study? ")
    intensity = input("What intensity level did you work at (low/medium/high)? ")

    # Log survey
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO surveys (survey_date, topic, notes) VALUES (?, ?, ?)",
              (datetime.now().date().isoformat(), topic, notes))
    conn.commit()
    conn.close()

    flashcards = generate_flashcards(topic, notes, depth, intensity)
    save_flashcards(topic, flashcards)

def generate_flashcards(topic, notes, depth, intensity):
    # This is an example for the POC, use LLMs to generate insightful cards.
    # If topic includes 'turing', output the example cards.
    if "turing" in topic.lower():
        return [
            ("What transitions do you need to build a machine that doubles the length of a unary word?",
             "Answer: [detailed transition explanation]"),
            ("What are the n elements needed for a Turing machine?",
             "Answer: starting state, alphabet, blank symbol, transition function, and accepting states"),
            ("In the case of shifting a word once to the right, how many final states does it make sense to have?",
             "Answer: Explanation and reasoning here...")
        ]
    # Otherwise, generate between 3 and 10 generic cards.
    num_cards = random.randint(3, 10)
    cards = []
    for i in range(num_cards):
        question = f"Question {i+1} about {topic}: What is the key point {i+1}?"
        answer = f"Answer {i+1}: Based on your notes: {notes[:20]}..."
        cards.append((question, answer))
    return cards

def save_flashcards(topic, flashcards):
    from datetime import datetime
    conn = get_connection()
    c = conn.cursor()
    for question, answer in flashcards:
        next_review = datetime.now().isoformat()
        # initial parameters: interval=1 day, ease_factor=2.5, repetitions=0.
        c.execute('''
            INSERT INTO flashcards (topic, question, answer, next_review, interval, ease_factor, repetitions, last_reviewed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (topic, question, answer, next_review, 1, 2.5, 0, datetime.now().isoformat()))
    conn.commit()
    conn.close()
