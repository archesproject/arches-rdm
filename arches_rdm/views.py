from collections import defaultdict

from django.contrib.auth import authenticate, login
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import CharField, F, OuterRef, Subquery, Value
from django.db.models.expressions import CombinedExpression, Func
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import View
from django_ratelimit.decorators import ratelimit


from arches.app.models.models import (
    Language,
    ResourceInstance,
    TileModel,
    Value as ConceptValue,
)
from arches.app.models.system_settings import settings
from arches.app.utils.betterJSONSerializer import JSONDeserializer, JSONSerializer
from arches.app.utils.decorators import group_required
from arches.app.utils.response import Http401Response, JSONErrorResponse, JSONResponse

from arches_rdm.const import (
    SCHEMES_GRAPH_ID,
    TOP_CONCEPT_OF_NODE_AND_NODEGROUP,
    BROADER_NODE_AND_NODEGROUP,
    CONCEPT_NAME_NODEGROUP,
    CONCEPT_NAME_CONTENT_NODE,
    CONCEPT_NAME_LANGUAGE_NODE,
    CONCEPT_NAME_TYPE_NODE,
    CONCEPT_IDENTIFIER_NODEGROUP,
    CONCEPT_IDENTIFIER_CONTENT_NODE,
    SCHEME_NAME_NODEGROUP,
    SCHEME_NAME_CONTENT_NODE,
    SCHEME_NAME_LANGUAGE_NODE,
    SCHEME_NAME_TYPE_NODE,
    SCHEME_IDENTIFIER_NODEGROUP,
    SCHEME_IDENTIFIER_CONTENT_NODE,
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
    group_required("RDM Administrator"), name="dispatch"
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
        # key=resourceid (str) val=identifier tile data
        # currently just concepts, not schemes
        self.identifiers: dict[str:dict] = defaultdict(dict)

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
    def nodegroup_subquery(nodegroup_id, annotating_resource=False):
        if annotating_resource:
            outer = OuterRef("resourceinstanceid")
        else:
            # Annotating a Tile
            outer = OuterRef("resourceinstance_id")

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
            .annotate(labels=self.nodegroup_subquery(CONCEPT_NAME_NODEGROUP))
            .annotate(identifiers=self.nodegroup_subquery(CONCEPT_IDENTIFIER_NODEGROUP))
            .values("resourceinstance_id", "top_concept_of", "labels", "identifiers")
        )
        for tile in top_concept_of_tiles:
            resource_id: str = str(tile["resourceinstance_id"])
            self.top_concepts[tile["top_concept_of"]].add(resource_id)
            self.labels[resource_id] = tile["labels"]
            if tile["identifiers"]:
                self.identifiers[resource_id] = tile["identifiers"][0]

    def narrower_concepts_map(self):
        broader_concept_tiles = (
            TileModel.objects.filter(nodegroup_id=BROADER_NODE_AND_NODEGROUP)
            .annotate(broader_concept=self.resources_from_tiles(BROADER_LOOKUP))
            .annotate(labels=self.nodegroup_subquery(CONCEPT_NAME_NODEGROUP))
            .annotate(identifiers=self.nodegroup_subquery(CONCEPT_IDENTIFIER_NODEGROUP))
            .values("resourceinstance_id", "broader_concept", "labels", "identifiers")
        )
        for tile in broader_concept_tiles.iterator():
            resource_id: str = str(tile["resourceinstance_id"])
            self.narrower_concepts[tile["broader_concept"]].add(resource_id)
            self.labels[resource_id] = tile["labels"]
            if tile["identifiers"]:
                self.identifiers[resource_id] = tile["identifiers"][0]

    def serialize_scheme(self, scheme: ResourceInstance):
        scheme_id: str = str(scheme.pk)
        return {
            "id": scheme_id,
            "labels": [self.serialize_scheme_label(label) for label in scheme.labels],
            "identifier": self.serialize_scheme_identifier(scheme.identifiers[0]) if scheme.identifiers else None,
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

    def serialize_scheme_identifier(self, identifier_tile: dict):
        for _lang_code, localized_string in identifier_tile[
            SCHEME_IDENTIFIER_CONTENT_NODE
        ].items():
            return localized_string["value"]

    def serialize_concept(self, conceptid: str):
        identifier = None
        if self.identifiers[conceptid]:
            identifier = list(
                self.identifiers[conceptid][CONCEPT_IDENTIFIER_CONTENT_NODE].values()
            )[0]["value"]

        return {
            "id": conceptid,
            "labels": [
                self.serialize_concept_label(label) for label in self.labels[conceptid]
            ],
            "identifier": identifier,
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

        self.schemes = (
            ResourceInstance.objects.filter(graph_id=SCHEMES_GRAPH_ID)
            .annotate(
                labels=self.nodegroup_subquery(
                    SCHEME_NAME_NODEGROUP, annotating_resource=True
                )
            )
            .annotate(
                identifiers=self.nodegroup_subquery(
                    SCHEME_IDENTIFIER_NODEGROUP, annotating_resource=True
                )
            )
        )

        data = {
            "schemes": [self.serialize_scheme(scheme) for scheme in self.schemes],
        }
        # Todo: filter by nodegroup permissions
        return JSONResponse(data)


class CsrfView(View):
    def get(self, request):
        token = get_token(request)
        return JSONResponse({"csrftoken": token})


class UserView(View):
    @method_decorator(ratelimit(key="post:username", rate=settings.RATE_LIMIT))
    def post(self, request):
        data = JSONDeserializer().deserialize(request.body)
        username = data.get("username", None)
        password = data.get("password", None)

        if not username or not password:
            return JSONErrorResponse(
                message=_("Please provide username and password."), status=400
            )

        user = authenticate(username=username, password=password)
        if user:
            userDict = JSONSerializer().serializeToPython(user)
            userDict["password"] = None
            response = JSONResponse(userDict)
            login(request, user)
        else:
            response = Http401Response()
            # Prevent browser auth modal
            del response["WWW-Authenticate"]

        return response
