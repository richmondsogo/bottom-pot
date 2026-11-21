from __future__ import annotations

from src.project_files.career_stage import classify_career_stage, is_early_career_stage


class TestCareerStageClassifier:
    def test_early_career_and_senior_level_i_precedence(self):
        assert classify_career_stage("Machine Learning Intern/Co-op (Winter 2027)") == "intern"
        assert classify_career_stage("2027 Software Developer Graduate Programme") == "graduate"
        assert classify_career_stage("Engineering Graduate Trainee") == "graduate"
        assert classify_career_stage("Software Engineering Apprentice") == "apprenticeship"
        assert classify_career_stage("Junior Data Scientist") == "junior"
        assert classify_career_stage("Software Engineer I, Backend") == "junior"
        assert classify_career_stage("Analyst, Early Career (Full Stack)") == "junior"
        assert classify_career_stage("Senior Software Engineer I") == "senior_plus"
        assert classify_career_stage("Principal Software Engineer I - CI/CD") == "senior_plus"
        assert classify_career_stage("Staff Platform Engineer") == "senior_plus"
        assert classify_career_stage("Software Engineer (Backend)") == "mid_or_unspecified"
        assert classify_career_stage(None) == "mid_or_unspecified"

        assert is_early_career_stage("intern") is True
        assert is_early_career_stage("graduate") is True
        assert is_early_career_stage("junior") is True
        assert is_early_career_stage("apprenticeship") is True
        assert is_early_career_stage("senior_plus") is False
        assert is_early_career_stage("mid_or_unspecified") is False
