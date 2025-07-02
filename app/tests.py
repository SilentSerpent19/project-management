from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Project, Employee, Task, Comment
from datetime import date

User = get_user_model()

class CommentDeleteViewTests(TestCase):
    def setUp(self):
        # Create users
        self.pm_user = User.objects.create_user(username='pm', password='pm123', role='pm')
        self.dev_user = User.objects.create_user(username='dev', password='dev123', role='dev')
        self.other_user = User.objects.create_user(username='other', password='other123', role='dev')
        # Use employees created by the signal
        self.pm_employee = Employee.objects.get(user=self.pm_user)
        self.dev_employee = Employee.objects.get(user=self.dev_user)
        self.other_employee = Employee.objects.get(user=self.other_user)
        # Create project
        self.project = Project.objects.create(name='Test Project', description='desc', upwork_id='u1', status='active')
        self.project.employees.set([self.pm_employee, self.dev_employee])
        # Create task
        self.task = Task.objects.create(
            project=self.project,
            main_employee=self.dev_employee,
            name='Test Task',
            status='todo',
            description='desc',
            due_date=date.today(),
            priority='medium',
        )
        # Create comment by dev
        self.comment = Comment.objects.create(
            task=self.task,
            employee=self.dev_employee,
            content='Test comment'
        )
        self.client = Client()

    def test_author_can_delete_comment(self):
        self.client.login(username='dev', password='dev123')
        url = reverse('comment_delete', args=[self.project.pk, self.task.pk, self.comment.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('comment_list', args=[self.project.pk, self.task.pk]))
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_pm_can_delete_comment(self):
        self.client.login(username='pm', password='pm123')
        url = reverse('comment_delete', args=[self.project.pk, self.task.pk, self.comment.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('comment_list', args=[self.project.pk, self.task.pk]))
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_other_user_cannot_delete_comment(self):
        self.client.login(username='other', password='other123')
        url = reverse('comment_delete', args=[self.project.pk, self.task.pk, self.comment.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_anonymous_cannot_delete_comment(self):
        url = reverse('comment_delete', args=[self.project.pk, self.task.pk, self.comment.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())
