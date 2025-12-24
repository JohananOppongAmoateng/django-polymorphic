"""
Tests for parent link field serialization in migrations.

This test module ensures that parent link fields with related_name='+'
are normalized to related_name=None to prevent migration churn.
"""

from django.db import models
from django.db.migrations.serializer import serializer_factory
from django.test import TestCase

from polymorphic.models import PolymorphicModel


class ParentLinkSerializationTest(TestCase):
    """
    Test that parent link fields with related_name='+' are normalized
    to prevent unnecessary migration generation.
    """

    def test_parent_link_related_name_plus_normalized(self):
        """
        Test that related_name='+' on parent link is normalized to None.
        
        When a parent link field is created with related_name='+', it should
        be normalized to related_name=None to match Django's auto-created
        parent links. This prevents migration churn.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test_parent_link"

        class ChildModel(BaseModel):
            # Manually create a parent link with related_name='+'
            basemodel_ptr = models.OneToOneField(
                BaseModel,
                on_delete=models.CASCADE,
                parent_link=True,
                related_name="+",
                primary_key=True,
            )
            age = models.IntegerField()

            class Meta:
                app_label = "test_parent_link"

        # Check the parent link field attributes
        parent_link = ChildModel._meta.get_field("basemodel_ptr")
        
        # The related_name should be normalized to None
        self.assertIsNone(parent_link.remote_field.related_name)
        self.assertIsNone(parent_link._related_name)

    def test_parent_link_deconstruction_excludes_related_name_plus(self):
        """
        Test that parent link field deconstruction does not include related_name='+'.
        
        This ensures that migrations won't contain related_name='+' for parent links,
        preventing unnecessary migration generation.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test_parent_link"

        class ChildModel(BaseModel):
            basemodel_ptr = models.OneToOneField(
                BaseModel,
                on_delete=models.CASCADE,
                parent_link=True,
                related_name="+",
                primary_key=True,
            )
            age = models.IntegerField()

            class Meta:
                app_label = "test_parent_link"

        parent_link = ChildModel._meta.get_field("basemodel_ptr")
        name, path, args, kwargs = parent_link.deconstruct()

        # related_name should not be in the deconstruct kwargs
        # when it's been normalized to None
        # Note: Django may still include it if None, but it won't be '+'
        if "related_name" in kwargs:
            self.assertIsNone(kwargs["related_name"])

    def test_parent_link_without_related_name_plus_unchanged(self):
        """
        Test that parent links without related_name='+' are not affected.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test_parent_link"

        class ChildModel(BaseModel):
            # Parent link with explicit related_name (not '+')
            basemodel_ptr = models.OneToOneField(
                BaseModel,
                on_delete=models.CASCADE,
                parent_link=True,
                related_name="child_link",
                primary_key=True,
            )
            age = models.IntegerField()

            class Meta:
                app_label = "test_parent_link"

        parent_link = ChildModel._meta.get_field("basemodel_ptr")
        
        # The related_name should not be changed
        self.assertEqual(parent_link.remote_field.related_name, "child_link")

    def test_parent_link_serialization_in_migration(self):
        """
        Test that parent link field serializes correctly for migrations.
        
        This simulates what happens during makemigrations to ensure
        the field serialization doesn't include related_name='+'.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test_parent_link"

        class ChildModel(BaseModel):
            basemodel_ptr = models.OneToOneField(
                BaseModel,
                on_delete=models.CASCADE,
                parent_link=True,
                related_name="+",
                primary_key=True,
            )
            age = models.IntegerField()

            class Meta:
                app_label = "test_parent_link"

        parent_link = ChildModel._meta.get_field("basemodel_ptr")
        serializer = serializer_factory(parent_link)
        serialized, imports = serializer.serialize()

        # The serialized field should not contain related_name='+'
        self.assertNotIn("related_name='+'", serialized)

    def test_non_parent_link_field_unchanged(self):
        """
        Test that non-parent-link fields with related_name='+' are not affected.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test_parent_link"

        class OtherModel(PolymorphicModel):
            # Regular foreign key with related_name='+'
            base = models.ForeignKey(BaseModel, on_delete=models.CASCADE, related_name="+")

            class Meta:
                app_label = "test_parent_link"

        fk_field = OtherModel._meta.get_field("base")
        
        # Non-parent-link fields should keep their related_name='+'
        self.assertEqual(fk_field.remote_field.related_name, "+")

    def test_auto_created_parent_link_unchanged(self):
        """
        Test that auto-created parent links are not affected.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "test_parent_link"

        class ChildModel(BaseModel):
            # No explicit parent link - Django will auto-create one
            age = models.IntegerField()

            class Meta:
                app_label = "test_parent_link"

        # Find the auto-created parent link
        parent_link = ChildModel._meta.get_field("basemodel_ptr")
        
        # Auto-created parent links should have related_name=None
        self.assertIsNone(parent_link.remote_field.related_name)
        self.assertTrue(parent_link.auto_created)
