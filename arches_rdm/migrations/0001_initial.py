from django.db import migrations
from django.utils.translation import gettext as _


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("models", "10121_workflowhistory"),
    ]

    def add_plugins(apps, schema_editor):
        Plugin = apps.get_model("models", "Plugin")

        Plugin(
            pluginid="29321ce0-bd95-4357-a2a5-822e9cb06f70",
            name=_("Lingo"),
            icon="fa fa-code-fork",
            component="App.vue",
            componentname="lingo",
            config={"show": True, "is_standalone": True},
            slug="lingo",
            sortorder=0,
        ).save()

    def remove_plugin(apps, schema_editor):
        Plugin = apps.get_model("models", "Plugin")
        Plugin.objects.filter(slug="lingo").delete()

    operations = [
        migrations.RunPython(add_plugins, remove_plugin),
    ]
