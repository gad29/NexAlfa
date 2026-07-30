"""
NexAlfa Graphify Backend
Manages the living knowledge graph using Graphify and Obsidian.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger("nex.memory.graphify")

class GraphifyBackend:
    """Wraps Graphify to build and query the local knowledge graph."""

    def __init__(self, target_dir: str = ".nex/memory_raw"):
        self.target_dir = Path(target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir = Path("graphify-out")
        
        # We store raw thoughts, code snippets, and memories in target_dir
        # Then we run graphify to build the graph and the Obsidian vault
        
    async def add_raw_memory(self, content: str, filename: str):
        """Save raw text to the memory directory so Graphify can process it."""
        try:
            file_path = self.target_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Added raw memory: {filename}")
        except Exception as e:
            logger.error(f"Failed to save raw memory {filename}: {e}")

    async def update_graph(self):
        """Run graphify --update --wiki to rebuild the graph and Obsidian vault."""
        logger.info("Triggering Graphify update pass...")
        try:
            # We run the graphify CLI on the target_dir
            # --update to only process new/changed files
            # --wiki to build the agent-crawlable markdown wiki (Obsidian)
            proc = await asyncio.create_subprocess_exec(
                "graphify", str(self.target_dir), "--update", "--wiki",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                logger.info("Graphify update complete.")
            else:
                err = stderr.decode() if stderr else "Unknown error"
                logger.warning(f"Graphify update failed (code {proc.returncode}): {err}")
                
        except Exception as e:
            logger.error(f"Graphify execution error: {e}")

    def get_wiki_index(self) -> str:
        """Read the index of the generated Graphify wiki for context."""
        index_path = self.out_dir / "wiki" / "index.md"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return ""

    def query_graph(self, query: str) -> str:
        """
        In a real Graphify integration, we'd query the graph.json here.
        For now, we'll just return the wiki index or use a local search over the wiki folder.
        """
        # Read the main index or god nodes to inject into agent prompt
        return self.get_wiki_index()

graphify_backend = GraphifyBackend()
