import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from arches.app.models.models import (
    Concept,
    GraphModel,
    Node,
    NodeGroup,
    ResourceInstance,
    TileModel,
    Value,
)

from arches_rdm.const import (
    ENGLISH_VALUE_ID,
    CONCEPTS_GRAPH_ID,
    LANGUAGE_CONCEPT_ID,
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
)


def setUpModule():
    """Bootstrap just a few nodes as an alternative to loading the entire package."""
    if not GraphModel.objects.filter(pk=SCHEMES_GRAPH_ID).exists():
        GraphModel.objects.create(pk=SCHEMES_GRAPH_ID, isresource=True)
        GraphModel.objects.create(pk=CONCEPTS_GRAPH_ID, isresource=True)

        for nodegroup_id, node_id, node_name, datatype in [
            (
                TOP_CONCEPT_OF_NODE_AND_NODEGROUP,
                TOP_CONCEPT_OF_NODE_AND_NODEGROUP,
                "Top concept of",
                "concept-list",
            ),
            (
                BROADER_NODE_AND_NODEGROUP,
                BROADER_NODE_AND_NODEGROUP,
                "Broader concept",
                "concept-list",
            ),
            (
                SCHEME_NAME_NODEGROUP,
                SCHEME_NAME_CONTENT_NODE,
                "Name content",
                "concept-list",
            ),
            (
                SCHEME_NAME_NODEGROUP,
                SCHEME_NAME_LANGUAGE_NODE,
                "Name language",
                "string",
            ),
            (
                CONCEPT_NAME_NODEGROUP,
                CONCEPT_NAME_CONTENT_NODE,
                "Name content",
                "concept-list",
            ),
            (
                CONCEPT_NAME_NODEGROUP,
                CONCEPT_NAME_LANGUAGE_NODE,
                "Name language",
                "string",
            ),
        ]:
            NodeGroup.objects.get_or_create(pk=nodegroup_id)
            Node.objects.create(
                pk=node_id,
                graph_id=CONCEPTS_GRAPH_ID,
                nodegroup_id=nodegroup_id,
                name=node_name,
                istopnode=False,
                datatype=datatype,
                isrequired=datatype == "string",
            )

    Concept.objects.get_or_create(
        conceptid=LANGUAGE_CONCEPT_ID,
        nodetype_id="Concept",
    )
    Value.objects.get_or_create(
        concept_id=LANGUAGE_CONCEPT_ID,
        valueid=ENGLISH_VALUE_ID,
        valuetype_id="prefLabel",
        value="en-US",
    )


def localized_string(text, language="en", direction="ltr"):
    return {language: {"value": text, "direction": direction}}


class ConceptTreeViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.admin = User.objects.get(username="admin")

    @classmethod
    def setUpTestData(cls):
        # Create a scheme with five concepts, each one narrower than the last,
        # and each concept after the top concept also narrower than the top.
        cls.scheme = ResourceInstance.objects.create(graph_id=SCHEMES_GRAPH_ID)
        TileModel.objects.create(
            resourceinstance=cls.scheme,
            nodegroup_id=SCHEME_NAME_NODEGROUP,
            data={
                SCHEME_NAME_CONTENT_NODE: localized_string("Test Scheme"),
                SCHEME_NAME_TYPE_NODE: [PREF_LABEL_VALUE_ID],
                SCHEME_NAME_LANGUAGE_NODE: [ENGLISH_VALUE_ID],
            },
        )

        MAX_DEPTH = 5
        CONCEPT_COUNT = 5
        cls.concepts = [
            ResourceInstance(graph_id=SCHEMES_GRAPH_ID) for _ in range(CONCEPT_COUNT)
        ]
        ResourceInstance.objects.bulk_create(cls.concepts)

        for i, concept in enumerate(cls.concepts):
            # Create label tile
            TileModel.objects.create(
                resourceinstance=concept,
                nodegroup_id=CONCEPT_NAME_NODEGROUP,
                data={
                    CONCEPT_NAME_CONTENT_NODE: localized_string(f"Concept {i + 1}"),
                    CONCEPT_NAME_TYPE_NODE: [PREF_LABEL_VALUE_ID],
                    CONCEPT_NAME_LANGUAGE_NODE: [ENGLISH_VALUE_ID],
                },
            )
            # Create top concept/narrower tile
            if i == 0:
                TileModel.objects.create(
                    resourceinstance=concept,
                    nodegroup_id=TOP_CONCEPT_OF_NODE_AND_NODEGROUP,
                    data={
                        TOP_CONCEPT_OF_NODE_AND_NODEGROUP: [
                            {"resourceId": str(cls.scheme.pk)},
                        ],
                    },
                )
            elif i < MAX_DEPTH:
                TileModel.objects.create(
                    resourceinstance=concept,
                    nodegroup_id=BROADER_NODE_AND_NODEGROUP,
                    data={
                        BROADER_NODE_AND_NODEGROUP: [
                            # Previous concept
                            {"resourceId": str(cls.concepts[i - 1].pk)},
                            # Also add top concept
                            {"resourceId": str(cls.concepts[0].pk)},
                        ],
                    },
                )
            else:
                TileModel.objects.create(
                    resourceinstance=concept,
                    nodegroup_id=BROADER_NODE_AND_NODEGROUP,
                    data={
                        BROADER_NODE_AND_NODEGROUP: [
                            # Top concept only
                            {"resourceId": str(cls.concepts[0].pk)},
                        ],
                    },
                )

    def test_get_concept_trees(self):
        self.client.force_login(self.admin)
        with self.assertNumQueries(6):
            # 1: session
            # 2: auth
            # 3: select languages, subquery for concept values
            # 4: select broader tiles, subquery for labels
            # 5: select top concept tiles, subquery for labels
            # 6: select schemes, subquery for labels
            response = self.client.get(reverse("concept_trees"))

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        scheme = result["schemes"][0]

        self.assertEqual(scheme["labels"][0]["value"], "Test Scheme")
        self.assertEqual(len(scheme["top_concepts"]), 1)
        top = scheme["top_concepts"][0]
        self.assertEqual(top["labels"][0]["value"], "Concept 1")
        self.assertEqual(len(top["narrower"]), 4)
        self.assertEqual(
            {n["labels"][0]["value"] for n in top["narrower"]},
            {"Concept 2", "Concept 3", "Concept 4", "Concept 5"},
        )
        concept_2 = [
            c for c in top["narrower"] if c["labels"][0]["value"] == "Concept 2"
        ][0]
        self.assertEqual(
            {n["labels"][0]["value"] for n in concept_2["narrower"]},
            {"Concept 3"},
        )
