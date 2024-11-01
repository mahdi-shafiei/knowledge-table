"""Query service."""

import logging
from typing import Any, Awaitable, Callable, List

from app.models.query_core import Chunk, FormatType, QueryType, Rule
from app.schemas.query_api import QueryResult, SearchResponse
from app.services.llm_service import (
    CompletionService,
    generate_inferred_response,
    generate_response,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SearchMethod = Callable[[str, str, List[Rule]], Awaitable[SearchResponse]]


def get_search_method(
    query_type: QueryType, vector_db_service: Any
) -> SearchMethod:
    """Get the search method based on the query type."""
    if query_type == "decomposition":
        return vector_db_service.decomposed_search
    elif query_type == "hybrid":
        return vector_db_service.hybrid_search
    else:  # simple_vector
        return lambda q, d, r: vector_db_service.vector_search([q], d)


def extract_chunks(search_response: SearchResponse) -> List[Chunk]:
    """Extract chunks from the search response."""
    return (
        search_response["chunks"]
        if isinstance(search_response, dict)
        else search_response.chunks
    )


def replace_keywords(text: str, keyword_replacements: dict[str, str]) -> str:
    """Replace keywords in text based on provided replacement dictionary."""
    if not text or not keyword_replacements:
        return text

    result = text
    for old_word, new_word in keyword_replacements.items():
        result = result.replace(old_word, new_word)
    return result


async def process_query(
    query_type: QueryType,
    query: str,
    document_id: str,
    rules: List[Rule],
    format: FormatType,
    llm_service: CompletionService,
    vector_db_service: Any,
) -> QueryResult:
    """Process the query based on the specified type."""
    search_method = get_search_method(query_type, vector_db_service)

    search_response = await search_method(query, document_id, rules)
    chunks = extract_chunks(search_response)
    concatenated_chunks = " ".join(chunk.content for chunk in chunks)

    answer = await generate_response(
        llm_service, query, concatenated_chunks, rules, format
    )
    answer_value = answer["answer"]

    # Extract and apply keyword replacements from all resolve_entity rules
    resolve_entity_rules = [
        rule for rule in rules if rule.type == "resolve_entity"
    ]

    replacements = {}
    if resolve_entity_rules and answer_value:
        # Combine all replacements from all resolve_entity rules
        for rule in resolve_entity_rules:
            if rule.options:
                rule_replacements = dict(
                    option.split(":") for option in rule.options
                )
                replacements.update(rule_replacements)

        if replacements:
            print(f"Resolving entities in answer: {answer_value}")
            answer_value = replace_keywords(answer_value, replacements)

    result_chunks = (
        []
        if answer_value in ("not found", None)
        and query_type != "decomposition"
        else chunks
    )

    return QueryResult(
        answer=answer_value,
        chunks=result_chunks[:10],
        resolved_entities=replacements if replacements else None,
    )


# Convenience functions for specific query types
async def decomposition_query(
    query: str,
    document_id: str,
    rules: List[Rule],
    format: FormatType,
    llm_service: CompletionService,
    vector_db_service: Any,
) -> QueryResult:
    """Process the query based on the decomposition type."""
    return await process_query(
        "decomposition",
        query,
        document_id,
        rules,
        format,
        llm_service,
        vector_db_service,
    )


async def hybrid_query(
    query: str,
    document_id: str,
    rules: List[Rule],
    format: FormatType,
    llm_service: CompletionService,
    vector_db_service: Any,
) -> QueryResult:
    """Process the query based on the hybrid type."""
    return await process_query(
        "hybrid",
        query,
        document_id,
        rules,
        format,
        llm_service,
        vector_db_service,
    )


async def simple_vector_query(
    query: str,
    document_id: str,
    rules: List[Rule],
    format: FormatType,
    llm_service: CompletionService,
    vector_db_service: Any,
) -> QueryResult:
    """Process the query based on the simple vector type."""
    return await process_query(
        "simple_vector",
        query,
        document_id,
        rules,
        format,
        llm_service,
        vector_db_service,
    )


async def inference_query(
    query: str,
    rules: List[Rule],
    format: FormatType,
    llm_service: CompletionService,
) -> QueryResult:
    """Generate a response, no need for vector retrieval."""
    # Since we are just answering this query based on data provided in the query,
    # ther is no need to retrieve any chunks from the vector database.

    answer = await generate_inferred_response(
        llm_service, query, rules, format
    )
    answer_value = answer["answer"]

    # Extract and apply keyword replacements from all resolve_entity rules
    resolve_entity_rules = [
        rule for rule in rules if rule.type == "resolve_entity"
    ]

    if resolve_entity_rules and answer_value:
        # Combine all replacements from all resolve_entity rules
        replacements = {}
        for rule in resolve_entity_rules:
            if rule.options:
                rule_replacements = dict(
                    option.split(":") for option in rule.options
                )
                replacements.update(rule_replacements)

        if replacements:
            print(f"Resolving entities in answer: {answer_value}")
            answer_value = replace_keywords(answer_value, replacements)

    return QueryResult(answer=answer_value, chunks=[])
