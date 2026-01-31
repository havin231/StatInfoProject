from app import create_app, db
from app.models import StudentAnswer, ExamResult

def regrade_all():
    app = create_app()
    with app.app_context():
        print("--- GLOBAL RE-GRADING TOOL ---")
        print("Scanning all student answers against current Answer Keys...")
        
        # 1. Fetch all answers in the system
        all_answers = StudentAnswer.query.all()
        
        answers_fixed = 0
        exams_to_recalc = set()
        
        # 2. Check every single answer
        for ans in all_answers:
            # The Source of Truth is the Question table
            current_key = ans.question.correct_answer
            
            # Check if the student's choice matches the CURRENT key
            should_be_correct = (ans.selected_option == current_key)
            
            # If the status in the DB is different from reality, fix it
            if ans.is_correct != should_be_correct:
                print(f" > Correction found: Exam ID {ans.exam_id}, Question {ans.question_id}")
                ans.is_correct = should_be_correct
                exams_to_recalc.add(ans.exam_id)
                answers_fixed += 1
        
        if answers_fixed == 0:
            print("\nEverything is already correct! No changes needed.")
            return

        print(f"\n{answers_fixed} individual answers corrected.")
        print(f"Recalculating scores for {len(exams_to_recalc)} exams...")
        
        # 3. Recalculate Scores for affected exams ONLY
        scores_updated = 0
        for exam_id in exams_to_recalc:
            exam = ExamResult.query.get(exam_id)
            if exam:
                total_questions = len(exam.answers)
                correct_count = sum(1 for a in exam.answers if a.is_correct)
                
                if total_questions > 0:
                    new_score = int((correct_count / total_questions) * 100)
                    if exam.score != new_score:
                        exam.score = new_score
                        scores_updated += 1
        
        # 4. Save
        db.session.commit()
        print(f"\nSUCCESS! {scores_updated} student final scores have been updated.")

if __name__ == "__main__":
    regrade_all()

