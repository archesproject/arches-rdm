from collections import defaultdict

from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import CharField, F, OuterRef, Subquery, Value
from django.db.models.expressions import CombinedExpression, Func
from django.utils.decorators import method_decorator
from django.views.generic import View

from arches.app.models.models import (
    Language,
    ResourceInstance,
    TileModel,
    Value as ConceptValue,
)
from arches.app.utils.decorators import group_required

from arches.app.utils.response import JSONResponse

from arches_rdm.const import (
    SCHEMES_GRAPH_ID,
    TOP_CONCEPT_OF_NODE_AND_NODEGROUP,
    BROADER_NODE_AND_NODEGROUP,
    CONCEPT_NAME_NODEGROUP,
    CONCEPT_NAME_CONTENT_NODE,
    CONCEPT_NAME_LANGUAGE_NODE,
    CONCEPT_NAME_TYPE_NODE,
    SCHEME_NAME_NODEGROUP,
    SCHEME_NAME_CONTENT_NODE,
    SCHEME_NAME_LANGUAGE_NODE,
    SCHEME_NAME_TYPE_NODE,
    PREF_LABEL_VALUE_ID,
    ALT_LABEL_VALUE_ID,
)

TOP_CONCEPT_OF_LOOKUP = f"data__{TOP_CONCEPT_OF_NODE_AND_NODEGROUP}"
BROADER_LOOKUP = f"data__{BROADER_NODE_AND_NODEGROUP}"


class JsonbArrayElements(Func):
    """https://forum.djangoproject.com/t/django-4-2-behavior-change-when-using-arrayagg-on-unnested-arrayfield-postgresql-specific/21547/5"""

    contains_subquery = True
    function = "JSONB_ARRAY_ELEMENTS"


@method_decorator(
    group_required("RDM Administrator", raise_exception=True), name="dispatch"
)
class ConceptTreeView(View):
    def __init__(self):
        self.schemes = ResourceInstance.objects.none()

        # Maps built during a GET call
        # key=concept valueid (str) val=language code
        self.language_concepts: dict[str:str] = {}
        # key=scheme resourceid (str) val=set of concept resourceids (str)
        self.top_concepts: dict[str : set[str]] = defaultdict(set)
        # key=concept resourceid (str) val=set of concept resourceids (str)
        self.narrower_concepts: dict[str : set[str]] = defaultdict(set)
        # key=resourceid (str) val=list of label dicts
        self.labels: dict[str : list[dict]] = defaultdict(set)

    @staticmethod
    def human_label_type(value_id):
        if value_id == PREF_LABEL_VALUE_ID:
            return "prefLabel"
        if value_id == ALT_LABEL_VALUE_ID:
            return "altLabel"
        return "unknown"

    @staticmethod
    def resources_from_tiles(lookup_expression: str):
        return CombinedExpression(
            JsonbArrayElements(F(lookup_expression)),
            "->>",
            Value("resourceId"),
            output_field=CharField(),
        )

    @staticmethod
    def labels_subquery(label_nodegroup):
        if label_nodegroup == SCHEME_NAME_NODEGROUP:
            # Annotating a ResourceInstance
            outer = OuterRef("resourceinstanceid")
            nodegroup_id = SCHEME_NAME_NODEGROUP
        else:
            # Annotating a Tile
            outer = OuterRef("resourceinstance_id")
            nodegroup_id = CONCEPT_NAME_NODEGROUP

        return ArraySubquery(
            TileModel.objects.filter(
                resourceinstance_id=outer, nodegroup_id=nodegroup_id
            ).values("data")
        )

    def language_concepts_map(self):
        languages = (
            Language.objects.all()
            .annotate(
                concept_value=Subquery(
                    ConceptValue.objects.filter(
                        valuetype="prefLabel", value=OuterRef("code")
                    ).values("valueid")
                )
            )
            .exclude(concept_value=None)
            .distinct()
        )
        for lang in languages:
            self.language_concepts[str(lang.concept_value)] = lang.code

    def top_concepts_map(self):
        top_concept_of_tiles = (
            TileModel.objects.filter(nodegroup_id=TOP_CONCEPT_OF_NODE_AND_NODEGROUP)
            .annotate(top_concept_of=self.resources_from_tiles(TOP_CONCEPT_OF_LOOKUP))
            .annotate(labels=self.labels_subquery(CONCEPT_NAME_NODEGROUP))
            .values("resourceinstance_id", "top_concept_of", "labels")
        )
        for tile in top_concept_of_tiles:
            resource_id: str = str(tile["resourceinstance_id"])
            self.top_concepts[tile["top_concept_of"]].add(resource_id)
            self.labels[resource_id] = tile["labels"]

    def narrower_concepts_map(self):
        broader_concept_tiles = (
            TileModel.objects.filter(nodegroup_id=BROADER_NODE_AND_NODEGROUP)
            .annotate(broader_concept=self.resources_from_tiles(BROADER_LOOKUP))
            .annotate(labels=self.labels_subquery(CONCEPT_NAME_NODEGROUP))
            .values("resourceinstance_id", "broader_concept", "labels")
        )
        for tile in broader_concept_tiles.iterator():
            resource_id: str = str(tile["resourceinstance_id"])
            self.narrower_concepts[tile["broader_concept"]].add(resource_id)
            self.labels[resource_id] = tile["labels"]

    def serialize_scheme(self, scheme: ResourceInstance):
        scheme_id: str = str(scheme.pk)
        return {
            "id": scheme_id,
            "labels": [self.serialize_scheme_label(label) for label in scheme.labels],
            "top_concepts": [
                self.serialize_concept(concept_id)
                for concept_id in self.top_concepts[scheme_id]
            ],
        }

    def serialize_scheme_label(self, label_tile: dict):
        lang_code = self.language_concepts[label_tile[SCHEME_NAME_LANGUAGE_NODE][0]]
        if lang_code in ("en-US", "en-us"):
            lang_code = "en"  # ETL process currently uses "en" as the language key
        try:
            value = label_tile[SCHEME_NAME_CONTENT_NODE][lang_code]["value"]
        except KeyError:
            value = "Unknown"
        return {
            "valuetype": self.human_label_type(label_tile[SCHEME_NAME_TYPE_NODE][0]),
            "language": lang_code,
            "value": value,
        }

    def serialize_concept(self, conceptid: str):
        return {
            "id": conceptid,
            "labels": [
                self.serialize_concept_label(label) for label in self.labels[conceptid]
            ],
            "narrower": [
                self.serialize_concept(conceptid)
                for conceptid in self.narrower_concepts[conceptid]
            ],
        }

    def serialize_concept_label(self, label_tile: dict):
        lang_code = self.language_concepts[label_tile[CONCEPT_NAME_LANGUAGE_NODE][0]]
        if lang_code in ("en-US", "en-us"):
            lang_code = "en"  # ETL process currently uses "en" as the language key
        try:
            value = label_tile[CONCEPT_NAME_CONTENT_NODE][lang_code]["value"]
        except KeyError:
            value = "Unknown"
        return {
            "valuetype": self.human_label_type(label_tile[CONCEPT_NAME_TYPE_NODE][0]),
            "language": lang_code,
            "value": value,
        }

    def get(self, request):
        self.language_concepts_map()
        self.top_concepts_map()
        self.narrower_concepts_map()

        self.schemes = ResourceInstance.objects.filter(
            graph_id=SCHEMES_GRAPH_ID
        ).annotate(labels=self.labels_subquery(SCHEME_NAME_NODEGROUP))

        data = {
            "schemes": [self.serialize_scheme(scheme) for scheme in self.schemes],
        }
        # Todo: filter by nodegroup permissions
        return JSONResponse(data)
