"""Document structures, serialization and comparison without application backends."""

__version__ = "0.1.0"

from .checks import CheckPolicy as CheckPolicy
from .checks import check_document as check_document
from .checks import compare_documents as compare_documents
from .color import (
    ColorSpace as ColorSpace,
)
from .color import (
    ColorValue as ColorValue,
)
from .composition import (
    DocumentIdMap as DocumentIdMap,
)
from .composition import (
    DocumentMerge as DocumentMerge,
)
from .composition import (
    IdentifierConflictPolicy as IdentifierConflictPolicy,
)
from .composition import (
    MetadataConflictPolicy as MetadataConflictPolicy,
)
from .composition import (
    PackagePolicy as PackagePolicy,
)
from .composition import (
    extract_document as extract_document,
)
from .composition import (
    merge_documents as merge_documents,
)
from .diagnostics import CheckResult as CheckResult
from .diagnostics import (
    ConversionIssue as ConversionIssue,
)
from .diagnostics import (
    ConversionReport as ConversionReport,
)
from .diagnostics import DiagnosticIssue as DiagnosticIssue
from .diagnostics import (
    IssueSeverity as IssueSeverity,
)
from .document_codec import (
    FORMAT_NAME as FORMAT_NAME,
)
from .document_codec import (
    FORMAT_VERSION as FORMAT_VERSION,
)
from .document_codec import (
    document_from_dict as document_from_dict,
)
from .document_codec import (
    document_from_json as document_from_json,
)
from .document_codec import (
    document_to_dict as document_to_dict,
)
from .document_codec import (
    document_to_json as document_to_json,
)
from .document_codec import (
    load_document as load_document,
)
from .document_codec import (
    save_document as save_document,
)
from .document_model import (
    VECTOR_IMAGE_MEDIA_TYPES as VECTOR_IMAGE_MEDIA_TYPES,
)
from .document_model import (
    Block as Block,
)
from .document_model import (
    Box as Box,
)
from .document_model import (
    ConversionMode as ConversionMode,
)
from .document_model import (
    DocumentModel as DocumentModel,
)
from .document_model import (
    Formula as Formula,
)
from .document_model import (
    FormulaFormat as FormulaFormat,
)
from .document_model import (
    Image as Image,
)
from .document_model import (
    ImageCrop as ImageCrop,
)
from .document_model import (
    ImageProperties as ImageProperties,
)
from .document_model import (
    Inline as Inline,
)
from .document_model import (
    Length as Length,
)
from .document_model import (
    PackageGraph as PackageGraph,
)
from .document_model import (
    PackagePart as PackagePart,
)
from .document_model import (
    PackageRelationship as PackageRelationship,
)
from .document_model import (
    PageSettings as PageSettings,
)
from .document_model import (
    Paragraph as Paragraph,
)
from .document_model import (
    ParagraphProperties as ParagraphProperties,
)
from .document_model import (
    Provenance as Provenance,
)
from .document_model import (
    ProvenanceEvent as ProvenanceEvent,
)
from .document_model import (
    Resource as Resource,
)
from .document_model import (
    ResourceKind as ResourceKind,
)
from .document_model import (
    Section as Section,
)
from .document_model import (
    SectionProperties as SectionProperties,
)
from .document_model import (
    Table as Table,
)
from .document_model import (
    TableCell as TableCell,
)
from .document_model import (
    TableCellProperties as TableCellProperties,
)
from .document_model import (
    TableProperties as TableProperties,
)
from .document_model import (
    TableRow as TableRow,
)
from .document_model import (
    TableRowProperties as TableRowProperties,
)
from .document_model import (
    TextRun as TextRun,
)
from .document_model import (
    TextStyle as TextStyle,
)
from .document_model import (
    TextStyleProperties as TextStyleProperties,
)
from .document_model import (
    VisualSurrogate as VisualSurrogate,
)
from .document_model import (
    attach_visual_surrogate as attach_visual_surrogate,
)
from .emphasis_quality import (
    EmphasisLossPolicy as EmphasisLossPolicy,
)
from .formula_quality_policy import (
    FormulaLossPolicy as FormulaLossPolicy,
)
from .inspection import (
    DocumentComparison as DocumentComparison,
)
from .inspection import (
    DocumentInspection as DocumentInspection,
)
from .inspection import (
    compare_inspections as compare_inspections,
)
from .inspection import (
    inspect_document_model as inspect_document_model,
)
from .limits import DocumentLimits as DocumentLimits
from .lists import LIST_PROPERTY as LIST_PROPERTY
from .lists import ListItem as ListItem
from .lists import ListKind as ListKind
from .lists import ListNumber as ListNumber
from .lists import get_list_item as get_list_item
from .lists import iter_list_items as iter_list_items
from .lists import iter_list_numbers as iter_list_numbers
from .lists import set_list_item as set_list_item
from .object_quality_policy import (
    ObjectLossPolicy as ObjectLossPolicy,
)
from .operations import (
    clone_model as clone_model,
)
from .operations import (
    extract_text as extract_text,
)
from .operations import (
    insert_node as insert_node,
)
from .operations import (
    remove_node as remove_node,
)
from .operations import (
    replace_node as replace_node,
)
from .operations import (
    transform_elements as transform_elements,
)
from .properties import (
    PROPERTY_SCHEMA_VERSION as PROPERTY_SCHEMA_VERSION,
)
from .quality_policy import (
    QualityPolicy as QualityPolicy,
)
from .resources import (
    ResourceConflictPolicy as ResourceConflictPolicy,
)
from .resources import (
    add_resource as add_resource,
)
from .resources import (
    embed_resources as embed_resources,
)
from .resources import (
    find_duplicate_resources as find_duplicate_resources,
)
from .resources import (
    find_resource_uses as find_resource_uses,
)
from .resources import (
    remove_resource as remove_resource,
)
from .resources import (
    replace_resource as replace_resource,
)
from .semantics import HEADING_PROPERTY as HEADING_PROPERTY
from .semantics import Heading as Heading
from .semantics import get_heading as get_heading
from .semantics import iter_headings as iter_headings
from .semantics import set_heading as set_heading
from .storage import ArtifactLimitError as ArtifactLimitError
from .styles import effective_text_style as effective_text_style
from .styles import resolve_style as resolve_style
from .text_quality_policy import (
    TextPreservationPolicy as TextPreservationPolicy,
)
from .traversal import (
    SECTION_CONTENT_FIELDS as SECTION_CONTENT_FIELDS,
)
from .traversal import (
    Element as Element,
)
from .traversal import (
    ModelNode as ModelNode,
)
from .traversal import (
    NodeKind as NodeKind,
)
from .traversal import (
    NodeLocation as NodeLocation,
)
from .traversal import (
    ResourceReference as ResourceReference,
)
from .traversal import (
    ResourceReferenceKind as ResourceReferenceKind,
)
from .traversal import (
    iter_blocks as iter_blocks,
)
from .traversal import (
    iter_elements as iter_elements,
)
from .traversal import (
    iter_inlines as iter_inlines,
)
from .traversal import (
    iter_resource_references as iter_resource_references,
)
from .traversal import (
    iter_sections as iter_sections,
)
from .traversal import (
    walk_model as walk_model,
)

__all__ = [
    "LIST_PROPERTY",
    "ListItem",
    "ListKind",
    "ListNumber",
    "get_list_item",
    "iter_list_items",
    "iter_list_numbers",
    "set_list_item",
    "HEADING_PROPERTY",
    "Heading",
    "get_heading",
    "iter_headings",
    "set_heading",
    "CheckPolicy",
    "CheckResult",
    "DiagnosticIssue",
    "check_document",
    "compare_documents",
    "ResourceConflictPolicy",
    "add_resource",
    "embed_resources",
    "find_duplicate_resources",
    "find_resource_uses",
    "remove_resource",
    "replace_resource",
    "effective_text_style",
    "resolve_style",
    "DocumentIdMap",
    "DocumentMerge",
    "IdentifierConflictPolicy",
    "MetadataConflictPolicy",
    "PackagePolicy",
    "extract_document",
    "merge_documents",
    "clone_model",
    "extract_text",
    "insert_node",
    "remove_node",
    "replace_node",
    "transform_elements",
    "SECTION_CONTENT_FIELDS",
    "Element",
    "ModelNode",
    "NodeKind",
    "NodeLocation",
    "ResourceReference",
    "ResourceReferenceKind",
    "iter_blocks",
    "iter_elements",
    "iter_inlines",
    "iter_resource_references",
    "iter_sections",
    "walk_model",
    "ArtifactLimitError",
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "PROPERTY_SCHEMA_VERSION",
    "VECTOR_IMAGE_MEDIA_TYPES",
    "Block",
    "Box",
    "ColorSpace",
    "ColorValue",
    "ConversionIssue",
    "ConversionMode",
    "ConversionReport",
    "DocumentComparison",
    "DocumentInspection",
    "DocumentModel",
    "DocumentLimits",
    "EmphasisLossPolicy",
    "Formula",
    "FormulaFormat",
    "FormulaLossPolicy",
    "Image",
    "ImageCrop",
    "ImageProperties",
    "Inline",
    "IssueSeverity",
    "Length",
    "ObjectLossPolicy",
    "PackageGraph",
    "PackagePart",
    "PackageRelationship",
    "PageSettings",
    "Paragraph",
    "ParagraphProperties",
    "Provenance",
    "ProvenanceEvent",
    "QualityPolicy",
    "Resource",
    "ResourceKind",
    "Section",
    "SectionProperties",
    "Table",
    "TableCell",
    "TableCellProperties",
    "TableProperties",
    "TableRow",
    "TableRowProperties",
    "TextPreservationPolicy",
    "TextRun",
    "TextStyle",
    "TextStyleProperties",
    "VisualSurrogate",
    "attach_visual_surrogate",
    "compare_inspections",
    "document_from_dict",
    "document_from_json",
    "document_to_dict",
    "document_to_json",
    "inspect_document_model",
    "load_document",
    "save_document",
]
