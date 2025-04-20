from core.memory import Memory
import json
import datetime

class EnhancedMemory(Memory):
    """
    Enhanced version of Memory class with improved storage and retrieval capabilities.
    Extends the base Memory class with structured data storage, tagging, and search functionality.
    """

    def __init__(self, history_length=25, max_kb_items=100):
        """
        Initialize enhanced memory with specified history and knowledge base capacity.
        
        Args:
            history_length (int): Maximum entries in history
            max_kb_items (int): Maximum items in knowledge base
        """
        super().__init__(history_length=history_length)
        self.knowledge_base = {}  # Structured knowledge storage
        self.kb_timestamps = {}   # When items were added
        self.kb_tags = {}         # Tags for items for better retrieval
        self.max_kb_items = max_kb_items
        
    def store_knowledge(self, key, value, tags=None):
        """
        Store important information in knowledge base with optional tags.
        
        Args:
            key (str): Unique identifier for this knowledge
            value (any): The content to store
            tags (list): Optional list of tags for categorization
        """
        # Clean up old items if we're at capacity
        if len(self.knowledge_base) >= self.max_kb_items:
            oldest_key = min(self.kb_timestamps.items(), key=lambda x: x[1])[0]
            self.remove_knowledge(oldest_key)
            
        # Store the new knowledge
        self.knowledge_base[key] = value
        self.kb_timestamps[key] = datetime.datetime.now()
        
        # Add tags if provided
        if tags:
            self.kb_tags[key] = [t.lower() for t in tags]
        else:
            self.kb_tags[key] = []
            
        # Add a structured entry in history about this new knowledge
        self.add_structured_entry(
            "Memory Storage", 
            f"Stored knowledge: '{key}' with tags: {tags or []}"
        )
        
    def retrieve_by_key(self, key):
        """Get knowledge by exact key"""
        if key in self.knowledge_base:
            return self.knowledge_base[key]
        return None
        
    def retrieve_by_tags(self, tags, require_all=False):
        """
        Find all knowledge items matching the given tags.
        
        Args:
            tags (list): Tags to search for
            require_all (bool): If True, item must have ALL tags; if False, ANY tag matches
            
        Returns:
            dict: Knowledge items matching the criteria
        """
        tags = [t.lower() for t in tags]
        results = {}
        
        for key, item_tags in self.kb_tags.items():
            if require_all:
                if all(tag in item_tags for tag in tags):
                    results[key] = self.knowledge_base[key]
            else:
                if any(tag in item_tags for tag in tags):
                    results[key] = self.knowledge_base[key]
                    
        return results
        
    def retrieve_related(self, query, limit=5):
        """
        Find knowledge related to the query based on simple keyword matching.
        More sophisticated implementations could use embeddings or other similarity measures.
        
        Args:
            query (str): The search query
            limit (int): Maximum number of results
            
        Returns:
            dict: Related knowledge items
        """
        query_terms = query.lower().split()
        scored_results = {}
        
        # Score each knowledge item based on term matches
        for key, value in self.knowledge_base.items():
            score = 0
            content = str(value).lower()
            
            # Score based on content match
            for term in query_terms:
                if term in content:
                    score += 1
                    
            # Extra points if term is in key
            for term in query_terms:
                if term in key.lower():
                    score += 2
                    
            # Extra points for tag matches
            for term in query_terms:
                if term in self.kb_tags.get(key, []):
                    score += 3
                    
            if score > 0:
                scored_results[key] = (value, score)
                
        # Sort by score and take top results
        sorted_results = sorted(scored_results.items(), 
                              key=lambda x: x[1][1], 
                              reverse=True)[:limit]
                              
        return {k: v[0] for k, v in sorted_results}
        
    def remove_knowledge(self, key):
        """Remove an item from knowledge base"""
        if key in self.knowledge_base:
            del self.knowledge_base[key]
            del self.kb_timestamps[key]
            if key in self.kb_tags:
                del self.kb_tags[key]
                
    def summarize_knowledge_base(self):
        """Get a summary of what's in the knowledge base"""
        summary = []
        
        # Group by tags
        tag_groups = {}
        for key, tags in self.kb_tags.items():
            for tag in tags or ["untagged"]:
                if tag not in tag_groups:
                    tag_groups[tag] = []
                tag_groups[tag].append(key)
                
        # Create summary
        for tag, keys in tag_groups.items():
            summary.append(f"- {tag.upper()}: {len(keys)} items - {', '.join(keys[:3])}" + 
                         (f"... and {len(keys)-3} more" if len(keys) > 3 else ""))
                
        return "\n".join(summary) if summary else "Knowledge base is empty"
        
    def get_all(self) -> str:
        """Override to include knowledge base summary"""
        memory_str = super().get_all()
        
        # Add knowledge base summary
        memory_str += "\n\nKnowledge Base Summary:\n"
        memory_str += self.summarize_knowledge_base()
        
        return memory_str