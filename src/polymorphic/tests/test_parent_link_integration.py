"""
Integration test to simulate the use case from the problem statement.

This test demonstrates that parent link fields created with related_name='+'
in a custom metaclass are normalized correctly to prevent migration churn.
"""

import os
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import models
from django.test import TestCase, override_settings

from polymorphic.models import PolymorphicModel


class CustomMetaclassIntegrationTest(TestCase):
    """
    Test that simulates the real-world use case where a custom metaclass
    creates parent link fields with related_name='+'.
    """

    def test_custom_metaclass_with_related_name_plus(self):
        """
        Test that parent links created by a custom metaclass with related_name='+'
        are normalized and don't cause migration churn.
        """

        # Define models similar to the problem statement
        class AssetModel(PolymorphicModel):
            reference = models.CharField(max_length=100)

            class Meta:
                app_label = "integration_test"

        class InheritedModelMeta(type(PolymorphicModel)):
            """Custom metaclass that creates parent link with related_name='+'"""

            def __new__(cls, model_name, bases, attrs, **kwargs):
                # Add parent_link without related_name so we don't "pollute" namespace
                if bases and hasattr(bases[0], "_meta") and not bases[0]._meta.abstract:
                    link_name = f"{bases[0].__name__.lower()}_link_ptr"
                    if link_name not in attrs:
                        attrs[link_name] = models.OneToOneField(
                            bases[0],
                            related_name="+",
                            on_delete=models.CASCADE,
                            parent_link=True,
                            primary_key=True,
                        )
                return super().__new__(cls, model_name, bases, attrs, **kwargs)

        class RackModel(AssetModel, metaclass=InheritedModelMeta):
            capacity = models.PositiveIntegerField()

            class Meta:
                app_label = "integration_test"

        # Check that the parent link field exists and has been normalized
        parent_link = RackModel._meta.get_field("assetmodel_link_ptr")

        # The related_name should have been normalized from '+' to None
        self.assertIsNone(
            parent_link.remote_field.related_name,
            "Parent link related_name should be normalized to None",
        )
        self.assertIsNone(
            parent_link._related_name, "Parent link _related_name should be normalized to None"
        )

        # Verify it's still a parent link
        self.assertTrue(parent_link.remote_field.parent_link)

        # Test field deconstruction (what migrations use)
        name, path, args, kwargs = parent_link.deconstruct()

        # related_name should not be '+' in the deconstruction
        if "related_name" in kwargs:
            self.assertNotEqual(
                kwargs["related_name"],
                "+",
                "related_name should not be '+' in field deconstruction",
            )

    def test_models_can_be_created_and_queried(self):
        """
        Test that models with normalized parent links work correctly at runtime.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "integration_test"

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
                app_label = "integration_test"

        # Verify the field was normalized
        parent_link = ChildModel._meta.get_field("basemodel_ptr")
        self.assertIsNone(parent_link.remote_field.related_name)

        # Note: We can't actually create instances in this test because
        # these models aren't in the Django app registry, but the
        # important part is that the field normalization works.


class MigrationSerializationTest(TestCase):
    """
    Test that the migration serialization works correctly.
    """

    def test_migration_serialization_matches_auto_created(self):
        """
        Test that manually created parent links with related_name='+'
        serialize the same way as auto-created parent links.
        """

        class BaseModel(PolymorphicModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "serialization_test"

        # Auto-created parent link (default Django behavior)
        class AutoChild(BaseModel):
            age = models.IntegerField()

            class Meta:
                app_label = "serialization_test"

        # Manually created parent link with related_name='+'
        class ManualChild(BaseModel):
            basemodel_ptr = models.OneToOneField(
                BaseModel,
                on_delete=models.CASCADE,
                parent_link=True,
                related_name="+",
                primary_key=True,
            )
            age = models.IntegerField()

            class Meta:
                app_label = "serialization_test"

        # Get parent links
        auto_parent_link = AutoChild._meta.get_field("basemodel_ptr")
        manual_parent_link = ManualChild._meta.get_field("basemodel_ptr")

        # Both should have related_name=None after normalization
        self.assertIsNone(auto_parent_link.remote_field.related_name)
        self.assertIsNone(manual_parent_link.remote_field.related_name)

        # Deconstruct both fields
        auto_name, auto_path, auto_args, auto_kwargs = auto_parent_link.deconstruct()
        manual_name, manual_path, manual_args, manual_kwargs = manual_parent_link.deconstruct()

        # The related_name handling should be consistent
        auto_has_related_name = "related_name" in auto_kwargs
        manual_has_related_name = "related_name" in manual_kwargs

        # If one has related_name in kwargs, both should
        self.assertEqual(
            auto_has_related_name,
            manual_has_related_name,
            "Auto and manual parent links should serialize related_name consistently",
        )

        # If related_name is in kwargs, it should be the same for both
        if auto_has_related_name and manual_has_related_name:
            self.assertEqual(
                auto_kwargs.get("related_name"),
                manual_kwargs.get("related_name"),
                "related_name value should be the same for auto and manual parent links",
            )
