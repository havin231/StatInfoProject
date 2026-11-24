"""
Tests for the exam engine and grading logic.
"""
from app.models import ExamResult


def test_exam_page_loads(client, sample_subject, sample_questions):
    """User can view the exam page without needing an account."""
    response = client.get(f'/subject/{sample_subject.slug}/exam')
    assert response.status_code == 200
    assert b'Mathematics Final Examination' in response.data
    assert b'What is 1 + 1?' in response.data
    assert b'What is 2 + 2?' in response.data
    assert b'What is 3 + 3?' in response.data


def test_exam_submission_perfect_score(client, sample_subject, sample_questions):
    """Submitting correct answers results in 100% and persists ExamResult."""
    form_data = {
        'taker_mode': 'guest',
        'taker_name': 'Guest Learner',
        'taker_birth_date': '2003-05-10',
        'taker_gender': 'male',
        f'q_{sample_questions[0].id}': 'A',
        f'q_{sample_questions[1].id}': 'A',
        f'q_{sample_questions[2].id}': 'A',
    }

    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Examination Submitted. Score: 3/3 (100%)' in response.data

    res = ExamResult.query.filter_by(subject_id=sample_subject.id).first()
    assert res is not None
    assert res.score == 100
    assert res.correct_count == 3
    assert res.total_questions == 3
    assert res.taker_gender == 'male'


def test_exam_submission_partial_score(client, sample_subject, sample_questions):
    """Submitting some incorrect answers calculates score correctly."""
    form_data = {
        'taker_mode': 'guest',
        'taker_name': 'Guest Learner',
        'taker_birth_date': '2003-05-10',
        'taker_gender': 'female',
        f'q_{sample_questions[0].id}': 'A',  # Correct
        f'q_{sample_questions[1].id}': 'B',  # Wrong
        f'q_{sample_questions[2].id}': 'C',  # Wrong
    }

    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Examination Submitted. Score: 1/3 (33%)' in response.data

    res = ExamResult.query.filter_by(subject_id=sample_subject.id).first()
    assert res is not None
    assert res.score == 33
    assert res.correct_count == 1
    assert res.total_questions == 3
    assert res.taker_gender == 'female'


def test_exam_partial_answer_not_100_percent(client, sample_subject, sample_questions):
    """Submitting only 1 answer out of 3 scores 33%, preventing partial-answer 100% exploit."""
    form_data = {
        'taker_mode': 'guest',
        'taker_birth_date': '2002-01-15',
        'taker_gender': 'male',
        f'q_{sample_questions[0].id}': 'A',
    }

    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Examination Submitted. Score: 1/3 (33%)' in response.data

    res = ExamResult.query.filter_by(subject_id=sample_subject.id).first()
    assert res is not None
    assert res.score == 33
    assert res.correct_count == 1
    assert res.total_questions == 3
