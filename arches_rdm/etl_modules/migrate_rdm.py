from datetime import datetime
import json
import logging
import uuid
from django.core.exceptions import ValidationError
from django.db import connection
from arches.app.datatypes.datatypes import DataTypeFactory
from arches.app.etl_modules.save import save_to_tiles
from arches.app.etl_modules.decorators import load_data_async
from arches.app.etl_modules.base_import_module import BaseImportModule, FileValidationError
from arches.app.models import models
from arches.app.models.concept import Concept
from arches.app.models.models import LoadStaging, NodeGroup, LoadEvent
from arches.app.utils.betterJSONSerializer import JSONSerializer
import arches_rdm.tasks as tasks

logger = logging.getLogger(__name__)

#### Constants ####
SCHEMES_GRAPH_ID = uuid.UUID("56788995-423b-11ee-8a8d-11afefc4bff7")
CONCEPTS_GRAPH_ID = uuid.UUID("bf73e576-4888-11ee-8a8d-11afefc4bff7")
CONCEPTS_TOP_CONCEPT_OF_NODEGROUP_ID = uuid.UUID("bf73e5b9-4888-11ee-8a8d-11afefc4bff7")
CONCEPTS_BROADER_NODEGROUP_ID = uuid.UUID("bf73e5f5-4888-11ee-8a8d-11afefc4bff7")
CONCEPTS_PART_OF_SCHEME_NODEGROUP_ID = uuid.UUID("bf73e60a-4888-11ee-8a8d-11afefc4bff7")


class RDMMigrator(BaseImportModule):
    def __init__(self, request=None, loadid=None):
        self.request = request if request else None
        self.userid = request.user.id if request else None
        self.moduleid = request.POST.get("module") if request else None
        self.loadid = request.POST.get("loadid") if request else loadid
        self.datatype_factory = DataTypeFactory()
    
    def etl_schemes(self, cursor, nodegroup_lookup, node_lookup):
        schemes = []
        for concept in models.Concept.objects.filter(nodetype="ConceptScheme").prefetch_related("value_set"):
            scheme_to_load = {"type": "Scheme", "tile_data": []}
            for value in concept.value_set.all():
                scheme_to_load["resourceinstanceid"] = concept.pk # use old conceptid as new resourceinstanceid

                name = {}
                identifier = {}
                if value.valuetype_id == "prefLabel" or value.valuetype_id == "altLabel":
                    name["name_content"] = value.value
                    name["name_language"] = value.language_id
                    name["name_type"] = value.valuetype_id
                    scheme_to_load["tile_data"].append({"name": name})
                elif value.valuetype_id == "identifier":
                    identifier["identifier_content"] = value.value
                    identifier["identifier_type"] = value.valuetype_id
                    scheme_to_load["tile_data"].append({"identifier": identifier})
            schemes.append(scheme_to_load)
        self.populate_staging_table(cursor, schemes, nodegroup_lookup, node_lookup)       

    def etl_concepts(self, cursor, nodegroup_lookup, node_lookup):
        concepts = []
        for concept in models.Concept.objects.filter(nodetype="Concept").prefetch_related("value_set"):
            concept_to_load = {"type": "Concept", "tile_data": []}
            for value in concept.value_set.all():
                concept_to_load["resourceinstanceid"] = concept.pk # use old conceptid as new resourceinstanceid

                name = {}
                identifier = {}
                if value.valuetype_id == "prefLabel" or value.valuetype_id == "altLabel":
                    name["name_content"] = value.value
                    name["name_language"] = value.language_id
                    name["name_type"] = value.valuetype_id
                    concept_to_load["tile_data"].append({"name": name})
                elif value.valuetype_id == "identifier":
                    identifier["identifier_content"] = value.value
                    identifier["identifier_type"] = value.valuetype_id
                    concept_to_load["tile_data"].append({"identifier": identifier})
            concepts.append(concept_to_load)
        self.populate_staging_table(cursor, concepts, nodegroup_lookup, node_lookup)


    def populate_staging_table(self, cursor, concepts_to_load, nodegroup_lookup, node_lookup):
        tiles_to_load = []
        for concept_to_load in concepts_to_load:
            for mock_tile in concept_to_load["tile_data"]:
                nodegroup_alias = next(iter(mock_tile.keys()), None)
                nodegroup_id = node_lookup[nodegroup_alias]["nodeid"]
                nodegroup_depth = nodegroup_lookup[nodegroup_id]["depth"]
                tile_id = uuid.uuid4()
                parent_tile_id = None
                tile_value_json, passes_validation = self.create_tile_value(cursor, mock_tile, nodegroup_alias, nodegroup_lookup, node_lookup)
                operation = "insert"
                tiles_to_load.append(LoadStaging(
                    load_event=LoadEvent(self.loadid),
                    nodegroup=NodeGroup(nodegroup_id),
                    resourceid=concept_to_load["resourceinstanceid"],
                    tileid=tile_id,
                    parenttileid=parent_tile_id,
                    value=tile_value_json,
                    nodegroup_depth=nodegroup_depth,
                    source_description="{0}: {1}".format(concept_to_load["type"], nodegroup_alias),  # source_description
                    passes_validation=passes_validation,
                    operation=operation,
                ))
        staged_tiles = LoadStaging.objects.bulk_create(tiles_to_load)
        
        cursor.execute("""CALL __arches_check_tile_cardinality_violation_for_load(%s)""", [self.loadid])
        cursor.execute(
            """
                INSERT INTO load_errors (type, source, error, loadid, nodegroupid)
                SELECT 'tile', source_description, error_message, loadid, nodegroupid
                FROM load_staging
                WHERE loadid = %s AND passes_validation = false AND error_message IS NOT null
            """,
            [self.loadid],
        )

    def create_tile_value(self, cursor, mock_tile, nodegroup_alias, nodegroup_lookup, node_lookup):
        tile_value = {}
        tile_valid = True
        for node_alias in mock_tile[nodegroup_alias].keys():
            try:
                nodeid = node_lookup[node_alias]["nodeid"]
                node_details = node_lookup[node_alias]
                datatype = node_details["datatype"]
                datatype_instance = self.datatype_factory.get_instance(datatype)
                source_value = mock_tile[nodegroup_alias][node_alias]
                config = node_details["config"]
                config["loadid"] = self.loadid
                config["nodeid"] = nodeid
                
                value, validation_errors = self.prepare_data_for_loading(datatype_instance, source_value, config)
                valid = True if len(validation_errors) == 0 else False
                if not valid:
                    tile_valid = False
                error_message = ""
                for error in validation_errors:
                    error_message = error["message"]
                    cursor.execute(
                        """INSERT INTO load_errors (type, value, source, error, message, datatype, loadid, nodeid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        ("node", source_value, "", error["title"], error["message"], datatype, self.loadid, nodeid),
                    )
                
                tile_value[nodeid] = {"value": value, "valid": valid, "source": source_value, "notes": error_message, "datatype": datatype}
            except KeyError:
                pass 

        return tile_value, tile_valid
    
    def init_relationships(self, cursor, loadid):
        # Create top concept of scheme relationships (derived from relations with 'hasTopConcept' relationtype)
        cursor.execute("""
           insert into load_staging(
                value,
                resourceid,
                tileid,
                passes_validation,
                nodegroup_depth,
                source_description,
                loadid,
                nodegroupid,
                operation
            )
            select 
                json_build_object(%s::uuid,
                    json_build_object(
                        'notes', '',
                        'valid', true,
                        'value', json_build_array(json_build_object('resourceId', conceptidfrom, 'ontologyProperty', '', 'resourceXresourceId', '', 'inverseOntologyProperty', '')),
                        'source', conceptidfrom,
                        'datatype', 'resource-instance-list'
                    )
                ) as value,
                conceptidto as resourceinstanceid, -- map target concept's new resourceinstanceid to its existing conceptid
                uuid_generate_v4() as tileid,
                true as passes_validation,
                0 as nodegroup_depth,
                'Scheme: top_concept_of' as source_description,
                %s::uuid as loadid,
                %s::uuid as nodegroupid,
                'insert' as operation
            from relations
            where relationtype = 'hasTopConcept';
        """, (CONCEPTS_TOP_CONCEPT_OF_NODEGROUP_ID, loadid, CONCEPTS_TOP_CONCEPT_OF_NODEGROUP_ID))

        # Create broader relationships (derived from relations with 'narrower' relationtype)
        cursor.execute("""
           insert into load_staging(
                value,
                resourceid,
                tileid,
                passes_validation,
                nodegroup_depth,
                source_description,
                loadid,
                nodegroupid,
                operation
            )
            select 
                json_build_object(%s::uuid,
                    json_build_object(
                        'notes', '',
                        'valid', true,
                        'value', json_build_array(json_build_object('resourceId', conceptidfrom, 'ontologyProperty', '', 'resourceXresourceId', '', 'inverseOntologyProperty', '')),
                        'source', conceptidfrom,
                        'datatype', 'resource-instance-list'
                    )
                ) as value,
                conceptidto as resourceinstanceid, -- map target concept's new resourceinstanceid to its existing conceptid
                uuid_generate_v4() as tileid,
                true as passes_validation,
                0 as nodegroup_depth,
                'Scheme: top_concept_of' as source_description,
                %s::uuid as loadid,
                %s::uuid as nodegroupid,
                'insert' as operation
            from relations
            where relationtype = 'narrower';
        """, (CONCEPTS_BROADER_NODEGROUP_ID, loadid, CONCEPTS_BROADER_NODEGROUP_ID))

        # Create Part of Scheme relationships - derived by recursively generating concept hierarchy & associating
        # concepts with their schemes
        cursor.execute("""
           insert into load_staging(
                value,
                resourceid,
                tileid,
                passes_validation,
                nodegroup_depth,
                source_description,
                loadid,
                nodegroupid,
                operation
            )
            WITH RECURSIVE concept_hierarchy AS (
                SELECT conceptidfrom AS root, conceptidto AS child, conceptidfrom AS parent_scheme
                FROM relations
                WHERE NOT EXISTS (
                    SELECT 1 FROM relations r2 WHERE r2.conceptidto = relations.conceptidfrom
                ) AND relationtype != 'member' -- only ETL'ing data into Lingo models, not collections
                UNION ALL
                SELECT ch.root, r.conceptidto, ch.parent_scheme
                FROM concept_hierarchy ch
                JOIN relations r ON ch.child = r.conceptidfrom
            )
            SELECT
                json_build_object(%s::uuid,
                    json_build_object(
                        'notes', '',
                        'valid', true,
                        'value', json_build_array(json_build_object('resourceId', parent_scheme, 'ontologyProperty', '', 'resourceXresourceId', '', 'inverseOntologyProperty', '')), --value
                        'source', parent_scheme,
                        'datatype', 'resource-instance-list'
                    )
                ) as value,
                child as resourceinstanceid, -- map target concept's new resourceinstanceid to its existing conceptid
                uuid_generate_v4() as tileid,
                true as passes_validation,
                0 as nodegroup_depth,
                'Concept: Part of Scheme' as source_description,
                %s::uuid as loadid,
                %s::uuid as nodegroupid,
                'insert' as operation
            FROM concept_hierarchy;
        """, (CONCEPTS_PART_OF_SCHEME_NODEGROUP_ID, loadid, CONCEPTS_PART_OF_SCHEME_NODEGROUP_ID))

    def start(self, request):
        load_details = {"operation": "RDM Migration"}
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO load_event (loadid, complete, status, etl_module_id, load_details, load_start_time, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (self.loadid, False, "running", self.moduleid, json.dumps(load_details), datetime.now(), self.userid),
        )
        message = "load event created"
        return {"success": True, "data": message}

    def write(self, request):
        self.loadid = request.POST.get("loadid")
        if models.Concept.objects.count() < 500:
            response = self.run_load_task(self.userid, self.loadid)
        else: 
            response = self.run_load_task_async(request, self.loadid)
        message = "RDM Migration Complete"
        return {"success": True, "data": message}

    def run_load_task(self, userid, loadid):
        self.loadid = loadid  # currently redundant, but be certain
        
        with connection.cursor() as cursor:

            # Gather and load schemes and concepts
            schemes_nodegroup_lookup, schemes_nodes = self.get_graph_tree(SCHEMES_GRAPH_ID)
            schemes_node_lookup = self.get_node_lookup(schemes_nodes)
            self.etl_schemes(cursor, schemes_nodegroup_lookup, schemes_node_lookup)

            concepts_nodegroup_lookup, concepts_nodes = self.get_graph_tree(CONCEPTS_GRAPH_ID)
            concepts_node_lookup = self.get_node_lookup(concepts_nodes)
            self.etl_concepts(cursor, concepts_nodegroup_lookup, concepts_node_lookup)

            # Create relationships
            self.init_relationships(cursor, loadid)

            # Validate and save to tiles
            validation = self.validate(loadid)
            if len(validation["data"]) == 0:
                cursor.execute(
                    """UPDATE load_event SET status = %s WHERE loadid = %s""",
                    ("validated", loadid),
                )
                response = save_to_tiles(userid, loadid)
                cursor.execute("""CALL __arches_update_resource_x_resource_with_graphids();""")
                cursor.execute("""SELECT __arches_refresh_spatial_views();""")
                refresh_successful = cursor.fetchone()[0]
                if not refresh_successful:
                    raise Exception('Unable to refresh spatial views')
                return response
            else:
                cursor.execute(
                    """UPDATE load_event SET status = %s, load_end_time = %s WHERE loadid = %s""",
                    ("failed", datetime.now(), loadid),
                )
                return {"success": False, "data": "failed"}

    @load_data_async
    def run_load_task_async(self, request):
        self.userid = request.user.id
        self.loadid = request.POST.get("loadid")

        migrate_rdm_task = tasks.migrate_rdm_task.apply_async(
            (self.userid, self.loadid),
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE load_event SET taskid = %s WHERE loadid = %s""",
                (migrate_rdm_task.task_id, self.loadid),
            )