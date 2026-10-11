export interface LibraryNode {
  id: string;
  itemId: string;
  title: string;
  kind: "video" | "article" | "post" | "profile";
  modality: "text" | "image";
  excerpt: string;
  url: string | null;
  thumbnailUrl: string | null;
  startSeconds: number | null;
  platform: string;
  language: string;
  tags: string[];
  contentType: string;
  attribution: string;
  collectionMethod: string;
  related: {
    nodeId: string;
    similarity: number;
    relation: "nearest" | "cross_modal";
  }[];
  indexed: boolean;
  x: number | null;
  y: number | null;
  score: number | null;
}
export interface CreatorLibrary {
  sourceType: "folder_import" | "youtube" | null;
  displayName: string;
  model: string;
  dimensions: number;
  itemCount: number;
  totalNodes: number;
  indexedNodes: number;
  omittedPassages: number;
  nodes: LibraryNode[];
  projection: "pca";
  errorMessage: string | null;
}
export interface LibrarySearch {
  mode: "semantic" | "lexical";
  matches: LibraryNode[];
}
