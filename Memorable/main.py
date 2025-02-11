# main.py
import threading, time, schedule
from db import init_db
from scheduler import schedule_jobs, review_flashcards

def cli_loop():
    from user_interface import main_menu
    while True:
        choice = main_menu()
        if choice == "1":
            from survey import run_daily_survey
            run_daily_survey()
        elif choice == "2":
            review_flashcards()
        elif choice == "3":
            print("Exiting...")
            exit(0)
        else:
            print("Invalid choice.")

def main():
    init_db()
    schedule_jobs()
    # Start CLI loop in a separate thread
    cli_thread = threading.Thread(target=cli_loop, daemon=True)
    cli_thread.start()
    # Main scheduling loop
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
