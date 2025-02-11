# scheduler.py
import schedule, time
from datetime import datetime
from db import get_connection
from flashcard import Flashcard
from notifications import send_notification
from config import DAILY_SURVEY_TIME, REVIEW_INTERVAL_MINUTES

def review_flashcards():
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT * FROM flashcards WHERE next_review <= ?", (now,))
    rows = c.fetchall()
    if not rows:
        send_notification("No flashcards due for review now.")
    for row in rows:
        card = Flashcard(
            id=row["id"],
            topic=row["topic"],
            question=row["question"],
            answer=row["answer"],
            next_review=row["next_review"],
            interval=row["interval"],
            ease_factor=row["ease_factor"],
            repetitions=row["repetitions"],
            last_reviewed=row["last_reviewed"]
        )
        print(f"\nTopic: {card.topic}\nQuestion: {card.question}")
        input("Press Enter to reveal the answer...")
        print(f"Answer: {card.answer}")
        try:
            quality = int(input("Rate your recall (0-5): "))
        except ValueError:
            quality = 0
        card.update(quality)
        c.execute('''
            UPDATE flashcards 
            SET next_review = ?, interval = ?, ease_factor = ?, repetitions = ?, last_reviewed = ?
            WHERE id = ?
        ''', (card.next_review.isoformat(), card.interval, card.ease_factor,
              card.repetitions, card.last_reviewed.isoformat(), card.id))
        conn.commit()
    conn.close()

def trigger_daily_survey():
    from survey import run_daily_survey
    run_daily_survey()

def schedule_jobs():
    # For demo, schedule reviews every REVIEW_INTERVAL_MINUTES.
    schedule.every(REVIEW_INTERVAL_MINUTES).minutes.do(review_flashcards)
    schedule.every().day.at(DAILY_SURVEY_TIME).do(trigger_daily_survey)
