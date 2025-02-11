from datetime import datetime, timedelta

class Flashcard:
    def __init__(self, id, topic, question, answer, next_review, interval, ease_factor, repetitions, last_reviewed):
        self.id = id
        self.topic = topic
        self.question = question
        self.answer = answer
        self.next_review = datetime.fromisoformat(next_review) if next_review else datetime.now()
        self.interval = interval
        self.ease_factor = ease_factor
        self.repetitions = repetitions
        self.last_reviewed = datetime.fromisoformat(last_reviewed) if last_reviewed else None

    def update(self, quality):
        # Simplified SM-2 algorithm
        if quality < 3:
            self.repetitions = 0
            self.interval = 1
        else:
            self.repetitions += 1
            if self.repetitions == 1:
                self.interval = 1
            elif self.repetitions == 2:
                self.interval = 6
            else:
                self.interval = int(self.interval * self.ease_factor)
        self.ease_factor = max(1.3, self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        self.last_reviewed = datetime.now()
        self.next_review = self.last_reviewed + timedelta(days=self.interval)

    def to_dict(self):
        return {
            "id": self.id,
            "topic": self.topic,
            "question": self.question,
            "answer": self.answer,
            "next_review": self.next_review.isoformat(),
            "interval": self.interval,
            "ease_factor": self.ease_factor,
            "repetitions": self.repetitions,
            "last_reviewed": self.last_reviewed.isoformat() if self.last_reviewed else None
        }
