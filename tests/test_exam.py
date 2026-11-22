"""
Tests for the exam engine and grading logic.
"""


def test_exam_page_loads(client, sample_subject, sample_questions):
    """User can view the exam page without needing an account."""
    response = client.get(f'/subject/{sample_subject.slug}/exam')
    assert response.status_code == 200
    assert b'Mathematics Final Examination' in response.data
    assert b'What is 1 + 1?' in response.data
    assert b'What is 2 + 2?' in response.data
    assert b'What is 3 + 3?' in response.data


def test_exam_submission_perfect_score(client, sample_subject, sample_questions):
    """Submitting correct answers results in 100%."""
    form_data = {
        f'q_{sample_questions[0].id}': 'A',
        f'q_{sample_questions[1].id}': 'A',
        f'q_{sample_questions[2].id}': 'A',
    }

    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Final Grade: 100%' in response.data


def test_exam_submission_partial_score(client, sample_subject, sample_questions):
    """Submitting some incorrect answers calculates score correctly."""
    form_data = {
        f'q_{sample_questions[0].id}': 'A',  # Correct
        f'q_{sample_questions[1].id}': 'B',  # Wrong
        f'q_{sample_questions[2].id}': 'C',  # Wrong
    }

    response = client.post(f'/subject/{sample_subject.slug}/exam/submit', data=form_data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Final Grade: 33%' in response.data
