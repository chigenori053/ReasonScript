use crate::semantic_planning::{SemanticPlanningEngine, SemanticPlanningError};
use crate::semantic_similarity::{SemanticSimilarityEngine, SemanticSimilarityError};
use crate::semantic_transformation::{
    SemanticTransformationEngine, SemanticTransformationError, TransformationPath,
};
use crate::semantic_type::{SemanticTypeError, SemanticTypeId, SemanticTypeRegistry};
use serde::{Deserialize, Serialize};
use std::fmt;

pub const SEMANTIC_SEARCH_VERSION: &str = "semantic-search-engine/0.1";
pub const SEARCH_RESULT_ITEM_NODE: &str = "SearchResultItem";
pub const SEARCH_RESULT_NODE: &str = "SearchResult";
pub const PATH_SEARCH_RESULT_NODE: &str = "PathSearchResult";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SearchKind {
    Ancestor,
    Descendant,
    Similarity,
    Reachability,
    Path,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SearchQuery {
    pub root: SemanticTypeId,
    pub kind: SearchKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<usize>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SearchResultItem {
    pub type_id: SemanticTypeId,
    pub score: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SearchResult {
    pub query: SearchQuery,
    pub items: Vec<SearchResultItem>,
}

impl SearchResult {
    pub fn to_json_pretty(&self) -> Result<String, SemanticSearchError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticSearchError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PathSearchResult {
    pub source: SemanticTypeId,
    pub target: SemanticTypeId,
    pub path: TransformationPath,
    pub distance: usize,
}

impl PathSearchResult {
    pub fn to_json_pretty(&self) -> Result<String, SemanticSearchError> {
        serde_json::to_string_pretty(self)
            .map_err(|error| SemanticSearchError::Serialization(error.to_string()))
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SearchResultItemIrNode {
    pub node_type: String,
    pub type_id: SemanticTypeId,
    pub score: f64,
}

impl From<&SearchResultItem> for SearchResultItemIrNode {
    fn from(item: &SearchResultItem) -> Self {
        Self {
            node_type: SEARCH_RESULT_ITEM_NODE.to_string(),
            type_id: item.type_id.clone(),
            score: item.score,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SearchResultIrNode {
    pub node_type: String,
    pub kind: SearchKind,
    pub items: Vec<SearchResultItemIrNode>,
}

impl From<&SearchResult> for SearchResultIrNode {
    fn from(result: &SearchResult) -> Self {
        Self {
            node_type: SEARCH_RESULT_NODE.to_string(),
            kind: result.query.kind,
            items: result
                .items
                .iter()
                .map(SearchResultItemIrNode::from)
                .collect(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PathSearchResultIrNode {
    pub node_type: String,
    pub distance: usize,
}

impl From<&PathSearchResult> for PathSearchResultIrNode {
    fn from(result: &PathSearchResult) -> Self {
        Self {
            node_type: PATH_SEARCH_RESULT_NODE.to_string(),
            distance: result.distance,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum SemanticSearchError {
    TypeHierarchy(SemanticTypeError),
    Similarity(SemanticSimilarityError),
    Transformation(SemanticTransformationError),
    Planning(SemanticPlanningError),
    PathQueryRequiresTarget,
    Serialization(String),
}

impl fmt::Display for SemanticSearchError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TypeHierarchy(error) => {
                write!(formatter, "semantic search hierarchy failed: {error}")
            }
            Self::Similarity(error) => {
                write!(formatter, "semantic similarity search failed: {error}")
            }
            Self::Transformation(error) => {
                write!(formatter, "semantic transformation search failed: {error}")
            }
            Self::Planning(error) => write!(formatter, "semantic path search failed: {error}"),
            Self::PathQueryRequiresTarget => {
                write!(formatter, "path search requires source and target type ids")
            }
            Self::Serialization(message) => {
                write!(formatter, "semantic search serialization failed: {message}")
            }
        }
    }
}

impl std::error::Error for SemanticSearchError {}

#[derive(Clone, Debug)]
pub struct SemanticSearchEngine {
    type_registry: SemanticTypeRegistry,
    similarity_engine: SemanticSimilarityEngine,
    transformation_engine: SemanticTransformationEngine,
    planning_engine: SemanticPlanningEngine,
}

impl SemanticSearchEngine {
    pub fn new(
        type_registry: SemanticTypeRegistry,
        similarity_engine: SemanticSimilarityEngine,
        transformation_engine: SemanticTransformationEngine,
        planning_engine: SemanticPlanningEngine,
    ) -> Self {
        Self {
            type_registry,
            similarity_engine,
            transformation_engine,
            planning_engine,
        }
    }

    pub fn type_registry(&self) -> &SemanticTypeRegistry {
        &self.type_registry
    }

    pub fn similarity_engine(&self) -> &SemanticSimilarityEngine {
        &self.similarity_engine
    }

    pub fn transformation_engine(&self) -> &SemanticTransformationEngine {
        &self.transformation_engine
    }

    pub fn planning_engine(&self) -> &SemanticPlanningEngine {
        &self.planning_engine
    }

    pub fn search(&self, query: SearchQuery) -> Result<SearchResult, SemanticSearchError> {
        match query.kind {
            SearchKind::Ancestor => self.ancestors_with_query(query),
            SearchKind::Descendant => self.descendants_with_query(query),
            SearchKind::Similarity => self.similar_with_query(query),
            SearchKind::Reachability => self.reachable_with_query(query),
            SearchKind::Path => Err(SemanticSearchError::PathQueryRequiresTarget),
        }
    }

    pub fn ancestors(&self, root: &SemanticTypeId) -> Result<SearchResult, SemanticSearchError> {
        self.search(SearchQuery {
            root: root.clone(),
            kind: SearchKind::Ancestor,
            limit: None,
        })
    }

    pub fn descendants(&self, root: &SemanticTypeId) -> Result<SearchResult, SemanticSearchError> {
        self.search(SearchQuery {
            root: root.clone(),
            kind: SearchKind::Descendant,
            limit: None,
        })
    }

    pub fn similar(
        &self,
        root: &SemanticTypeId,
        limit: usize,
    ) -> Result<SearchResult, SemanticSearchError> {
        self.search(SearchQuery {
            root: root.clone(),
            kind: SearchKind::Similarity,
            limit: Some(limit),
        })
    }

    pub fn reachable(&self, root: &SemanticTypeId) -> Result<SearchResult, SemanticSearchError> {
        self.search(SearchQuery {
            root: root.clone(),
            kind: SearchKind::Reachability,
            limit: None,
        })
    }

    pub fn path(
        &self,
        source: &SemanticTypeId,
        target: &SemanticTypeId,
    ) -> Result<PathSearchResult, SemanticSearchError> {
        let plan = self
            .planning_engine
            .shortest_plan(source, target)
            .map_err(SemanticSearchError::Planning)?;
        let mut nodes = Vec::with_capacity(plan.steps.len() + 1);
        nodes.push(plan.start);
        nodes.extend(plan.steps.into_iter().map(|step| step.target));
        let path = TransformationPath { nodes };

        Ok(PathSearchResult {
            source: source.clone(),
            target: target.clone(),
            distance: path.nodes.len().saturating_sub(1),
            path,
        })
    }

    fn ancestors_with_query(
        &self,
        query: SearchQuery,
    ) -> Result<SearchResult, SemanticSearchError> {
        let items = self
            .type_registry
            .get_ancestors(&query.root)
            .map_err(SemanticSearchError::TypeHierarchy)?
            .into_iter()
            .map(unit_score)
            .collect();
        Ok(result_with_limit(query, items))
    }

    fn descendants_with_query(
        &self,
        query: SearchQuery,
    ) -> Result<SearchResult, SemanticSearchError> {
        let items = self
            .type_registry
            .get_descendants(&query.root)
            .map_err(SemanticSearchError::TypeHierarchy)?
            .into_iter()
            .map(unit_score)
            .collect();
        Ok(result_with_limit(query, items))
    }

    fn similar_with_query(&self, query: SearchQuery) -> Result<SearchResult, SemanticSearchError> {
        let limit = query.limit.unwrap_or(usize::MAX);
        let items = self
            .similarity_engine
            .nearest_neighbors(&query.root, limit)
            .map_err(SemanticSearchError::Similarity)?
            .neighbors
            .into_iter()
            .map(|neighbor| SearchResultItem {
                type_id: neighbor.right,
                score: neighbor.similarity,
            })
            .collect();
        Ok(SearchResult { query, items })
    }

    fn reachable_with_query(
        &self,
        query: SearchQuery,
    ) -> Result<SearchResult, SemanticSearchError> {
        let mut type_ids = self
            .type_registry
            .get_ancestors(&query.root)
            .map_err(SemanticSearchError::TypeHierarchy)?;
        type_ids.extend(
            self.type_registry
                .get_descendants(&query.root)
                .map_err(SemanticSearchError::TypeHierarchy)?,
        );
        let items = type_ids.into_iter().map(unit_score).collect();
        Ok(result_with_limit(query, items))
    }
}

fn unit_score(type_id: SemanticTypeId) -> SearchResultItem {
    SearchResultItem {
        type_id,
        score: 1.0,
    }
}

fn result_with_limit(query: SearchQuery, mut items: Vec<SearchResultItem>) -> SearchResult {
    if let Some(limit) = query.limit {
        items.truncate(limit);
    }
    SearchResult { query, items }
}
