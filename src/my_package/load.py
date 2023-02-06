from pathlib import Path

import pandas as pd
from csvcubed.cli.inspect.metadatainputvalidator import MetadataValidator
from csvcubed.cli.inspect.metadataprinter import (
    MetadataPrinter,
    to_absolute_rdflib_file_path,
)
from csvcubed.utils.tableschema import CsvwRdfManager
from csvcubed.utils.sparql_handler.data_cube_state import DataCubeState

# Class that builds a pandas dataframe from csv file
# Class also updates dataframe to use 'Lables' values instead of 'Notation' values
class buildDataFrame:

    # Hardcoded json path
    # Should point to main metadata.json file provided by users in their CSVW
    csvw_metadata_json_path = Path(
        "/Users/gregorypavier/project_dir/out/sweden-at-eurovision.csv-metadata.json"
        # "/Users/gregorypavier/project_dir/out/ambulanc_response_times/ambulance-response-times-by-local-authority.csv-metadata.json"
    )

    # Directory that contains csv files
    csvw_directory = (
        "/Users/gregorypavier/project_dir/out/"
        # "/Users/gregorypavier/project_dir/out/ambulance_responses_times/"
    )

    csvw_rdf_manager = CsvwRdfManager(csvw_metadata_json_path)
    csvw_metadata_rdf_graph = csvw_rdf_manager.rdf_graph

    csvw_metadata_rdf_validator = MetadataValidator(
        csvw_metadata_rdf_graph, csvw_metadata_json_path
    )

    csvw_type = csvw_metadata_rdf_validator.detect_csvw_type()

    data_cube = DataCubeState(
        csvw_rdf_manager.rdf_graph, csvw_rdf_manager.csvw_metadata_file_path
    )

    metadata_printer = MetadataPrinter(
        csvw_type=csvw_type,
        csvw_metadata_rdf_graph=csvw_metadata_rdf_graph,
        csvw_metadata_json_path=csvw_metadata_json_path,
        data_cube_state=data_cube,
        code_list_state=None,
    )

    metadata_printer.generate_general_results()

    dataset_uri = to_absolute_rdflib_file_path(
        metadata_printer.result_catalog_metadata.dataset_uri, csvw_metadata_json_path
    )

    cube_identifiers = data_cube.get_cube_identifiers_for_data_set(
        metadata_printer.result_catalog_metadata.dataset_uri
    )
    dsd_components = data_cube.get_dsd_qube_components_for_csv(cube_identifiers.csv_url)
    cube_shape = data_cube.get_shape_for_csv(cube_identifiers.csv_url)
    csv_path = csvw_metadata_json_path.parent / cube_identifiers.csv_url

    data = pd.read_csv(csv_path)

    obs_val_columns = set(data.columns) - {
        col.title
        for component in dsd_components.qube_components
        for col in component.real_columns_used_in
    }
    obs_val_column_title = obs_val_columns.pop()

    dimension_column_titles = {
        col.title
        for component in dsd_components.qube_components
        for col in component.real_columns_used_in
        if component.property_type == "Dimension"
        and component.property != "http://purl.org/linked-data/cube#measureType"
    }

    measure_columns = {
        col.title
        for component in dsd_components.qube_components
        for col in component.real_columns_used_in
        if component.property_type == "Dimension"
        and component.property == "http://purl.org/linked-data/cube#measureType"
    }
    measure_column_title = measure_columns.pop()

    measure_dict = {
        str(component.property).split("/")[-1]: component.property_label
        for component in dsd_components.qube_components
        if component.property_type == "Measure"
    }

    units_columns = {
        col.title
        for component in dsd_components.qube_components
        for col in component.real_columns_used_in
        if component.property_type == "Attribute"
        and component.property
        == "http://purl.org/linked-data/sdmx/2009/attribute#unitMeasure"
    }
    units_column_title = units_columns.pop()

    # dimension_column_titles corresponds to individual csv files that are referenced by the main eurovision csv
    # The eurovision csv uses the 'Notation' values which are all lowercase and can contain '-'s
    # Therefore, for cleanliness, we will replace these values with the more presentable 'Label' values
    for dim in dimension_column_titles:
        data[dim] = data[dim].astype("category")
        if Path(csvw_directory + str(dim).lower() + ".csv").exists():
            replace_df = pd.read_csv(csvw_directory + str(dim).lower() + ".csv")
            replace_dict = replace_df.set_index("Notation").to_dict()["Label"]
            data[dim] = data[dim].cat.rename_categories(replace_dict)

    data[measure_column_title] = data[measure_column_title].astype("category")
    data[measure_column_title] = data[measure_column_title].cat.rename_categories(
        measure_dict
    )
