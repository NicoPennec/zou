import datetime
import os
import tempfile

from tests.base import ApiDBTestCase

from zou.app.models.task import Task

from zou.app.services import comments_service


class ImportCsvTaskTypeEstimationsTestCase(ApiDBTestCase):
    def setUp(self):
        super(ImportCsvTaskTypeEstimationsTestCase, self).setUp()

        self.generate_fixture_project_status()
        self.generate_fixture_project()
        self.generate_fixture_department()
        self.generate_fixture_task_type()
        self.generate_fixture_person()
        self.generate_fixture_assigner()
        # Creates sequence "S01", shot "P01" and an Animation task on it.
        self.generate_fixture_shot_task()
        self.task_type_id = self.task_type_animation.id
        self.path = (
            f"/import/csv/projects/{self.project.id}"
            f"/task-types/{self.task_type_id}/estimations"
        )

    def write_csv(self, content):
        """
        Write CSV content to a temporary file and return its path.
        """
        descriptor, file_path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def import_csv(self, content, code=201):
        return self.upload_file(self.path, self.write_csv(content), code)

    def test_import_real_dates(self):
        content = (
            "Parent,Entity,Estimation,Start date,Due date,Difficulty,"
            "WIP date,Feedback date,Approval date\n"
            "S01,P01,2,2024-01-01,2024-01-10,3,"
            "2024-01-05,2024-01-20,2024-01-25\n"
        )
        self.import_csv(content)

        task = Task.get(self.shot_task.id)
        # New real-date columns
        self.assertEqual(
            task.real_start_date.strftime("%Y-%m-%d"), "2024-01-05"
        )
        self.assertEqual(task.end_date.strftime("%Y-%m-%d"), "2024-01-20")
        self.assertEqual(task.done_date.strftime("%Y-%m-%d"), "2024-01-25")
        # Existing columns still work (backward compatibility)
        self.assertEqual(task.start_date.strftime("%Y-%m-%d"), "2024-01-01")
        self.assertEqual(task.due_date.strftime("%Y-%m-%d"), "2024-01-10")
        self.assertEqual(task.difficulty, 3)
        self.assertIsNotNone(task.estimation)

    def test_import_empty_real_dates_are_skipped(self):
        # Pre-set the real-date columns then import empty cells: empty cells
        # follow the existing convention (skip, do not null the field).
        self.shot_task.update(
            {
                "real_start_date": datetime.datetime(2023, 12, 1),
                "end_date": datetime.datetime(2023, 12, 2),
                "done_date": datetime.datetime(2023, 12, 3),
            }
        )
        content = (
            "Parent,Entity,WIP date,Feedback date,Approval date\n"
            "S01,P01,,,\n"
        )
        self.import_csv(content)

        task = Task.get(self.shot_task.id)
        self.assertEqual(
            task.real_start_date.strftime("%Y-%m-%d"), "2023-12-01"
        )
        self.assertEqual(task.end_date.strftime("%Y-%m-%d"), "2023-12-02")
        self.assertEqual(task.done_date.strftime("%Y-%m-%d"), "2023-12-03")

    def test_imported_real_start_date_survives_wip_transition(self):
        # An imported real_start_date (admin override) must not be overwritten
        # when the task later transitions to a WIP status, since the auto-set
        # only fills the field when it is null.
        content = "Parent,Entity,WIP date\nS01,P01,2024-01-05\n"
        self.import_csv(content)

        task_status_wip = self.generate_fixture_task_status_wip()
        comments_service.create_comment(
            self.person.id,
            str(self.shot_task.id),
            task_status_wip.id,
            "Moving to WIP",
        )

        task = Task.get(self.shot_task.id)
        self.assertEqual(
            task.real_start_date.strftime("%Y-%m-%d"), "2024-01-05"
        )
