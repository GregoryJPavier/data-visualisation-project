from pathlib import Path

import pandas as pd
from csvcubed.cli.inspect.inspect import _generate_printables
from csvcubed.cli.inspect.metadatainputvalidator import MetadataValidator
from csvcubed.cli.inspect.metadataprinter import (
    MetadataPrinter,
    to_absolute_rdflib_file_path,
)
from csvcubed.utils.sparql_handler.sparqlmanager import (
    select_csvw_dsd_qube_components,
    select_qb_dataset_url,
)
from csvcubed.utils.tableschema import CsvwRdfManager

# Hardcoded json path
# Should point to main metadata.json file provided by users in their CSVW
csvw_metadata_json_path = Path(
    # "/Users/gregorypavier/project_dir/out/sweden-at-eurovision-no-missing.csv-metadata.json"
    "/Users/gregorypavier/project_dir/out/ambulanc_response_times/ambulance-response-times-by-local-authority.csv-metadata.json"
)

# Directory that contains csv files
csvw_dimension_columns_path = (
    #"/Users/gregorypavier/project_dir/out/"
    "/Users/gregorypavier/project_dir/out/ambulance_responses_times/"
)

csvw_rdf_manager = CsvwRdfManager(csvw_metadata_json_path)
csvw_metadata_rdf_graph = csvw_rdf_manager.rdf_graph

csvw_metadata_rdf_validator = MetadataValidator(
    csvw_metadata_rdf_graph, csvw_metadata_json_path
)

(
    valid_csvw_metadata,
    csvw_type,
) = csvw_metadata_rdf_validator.validate_and_detect_type()

if valid_csvw_metadata:
    (
        type_printable,
        catalog_metadata_printable,
        dsd_info_printable,
        codelist_info_printable,
        dataset_observations_printable,
        val_counts_by_measure_unit_printable,
        codelist_hierarchy_info_printable,
    ) = _generate_printables(
        csvw_type, csvw_metadata_rdf_graph, csvw_metadata_json_path
    )
else:
    print("CSV-W didn't appear to be valid")

metadata_printer = MetadataPrinter(
    csvw_type, csvw_metadata_rdf_graph, csvw_metadata_json_path
)

metadata_printer.generate_general_results()

dsd_components = select_csvw_dsd_qube_components(
    csvw_metadata_rdf_graph,
    metadata_printer.result_dataset_label_dsd_uri.dsd_uri,
    csvw_metadata_json_path,
)

dataset_uri = to_absolute_rdflib_file_path(
    metadata_printer.result_catalog_metadata.dataset_uri, csvw_metadata_json_path
)
csv_path = (
    csvw_metadata_json_path.parent
    / select_qb_dataset_url(csvw_metadata_rdf_graph, dataset_uri).dataset_url
)

# Class that builds a pandas dataframe from csv file
# Class also updates dataframe to use 'Lables' values instead of 'Notation' values
class buildDataFrame:

    data = pd.read_csv(csv_path)

    obs_val_columns = set(data.columns) - {
        component.csv_col_title for component in dsd_components.qube_components
    }
    obs_val_column_title = obs_val_columns.pop()

    dimension_column_titles = {
        component.csv_col_title
        for component in dsd_components.qube_components
        if component.property_type == "Dimension"
        and component.property != "http://purl.org/linked-data/cube#measureType"
    }

    measure_columns = {
        component.csv_col_title
        for component in dsd_components.qube_components
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
        component.csv_col_title
        for component in dsd_components.qube_components
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
        if Path(csvw_dimension_columns_path + str(dim).lower() + ".csv").exists():
            replace_df = pd.read_csv(
                csvw_dimension_columns_path + str(dim).lower() + ".csv"
            )
            replace_dict = replace_df.set_index("Notation").to_dict()["Label"]
            data[dim] = data[dim].cat.rename_categories(replace_dict)

    # data[obs_val_column_title] = data[obs_val_column_title].astype("int")

    data[measure_column_title] = data[measure_column_title].astype("category")
    data[measure_column_title] = data[measure_column_title].cat.rename_categories(
        measure_dict
    )
