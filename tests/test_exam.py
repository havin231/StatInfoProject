"""
Tests for the exam engine and grading logic.
"""
from app.models import ExamResult, StudentAnswer


def test_exam_page_loads(client, sample_student, sample_subject, sample_questions):
    """Student can view the exam page."""
    # Login as student
    client.post('/student/login', data={'access_code': 'ABC123'})
    
    # Access exam
    response = client.get(f'/subject/{sample_subject.slug}/exam')
    assert response.status_code == 200
    assert b'Mathematics Final Examination' in response.data
    assert b'What is 1 + 1?' in response.data
    assert b'What is 2 + 2?' in response.data
    assert b'What is 3 + 3?' in response.data


def test_exam_submission_perfect_score(client, db, sample_student, sample_subject, sample_questions):
    """Submitting correct answers results in 100%."""
    client.post('/student/login', data={'access_code': 'ABC123'})
    
    # Prepare form data: all correct answers are 'A'
    form_data = {
        f'q_{sample_questions[0].id}': 'A',
        f'q_{sample_questions[1].id}': 'A',
        f'q_{sample_questions[2].id}': 'A',
    }
    
    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Final Grade: 100%' in response.data
    
    # Verify DB
    result = ExamResult.query.filter_by(student_id=sample_student.id).first()
    assert result is not None
    assert result.score == 100
    assert len(result.answers) == 3


def test_exam_submission_partial_score(client, db, sample_student, sample_subject, sample_questions):
    """Submitting some incorrect answers calculates score correctly."""
    client.post('/student/login', data={'access_code': 'ABC123'})
    
    # Prepare form data: 1 correct, 2 incorrect
    form_data = {
        f'q_{sample_questions[0].id}': 'A', # Correct
        f'q_{sample_questions[1].id}': 'B', # Wrong
        f'q_{sample_questions[2].id}': 'C', # Wrong
    }
    
    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    
    # Integer math: 1/3 = 33%
    assert b'Final Grade: 33%' in response.data
    
    result = ExamResult.query.filter_by(student_id=sample_student.id).first()
    assert result.score == 33
    
    # Verify individual answer correctness logs
    correct_ans = StudentAnswer.query.filter_by(exam_id=result.id, is_correct=True).count()
    wrong_ans = StudentAnswer.query.filter_by(exam_id=result.id, is_correct=False).count()
    assert correct_ans == 1
    assert wrong_ans == 2
