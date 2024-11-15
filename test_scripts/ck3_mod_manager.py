import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict
import aiofiles
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class ModValidation:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class CK3ModManager:
    """CK3 Mod Development and Management System"""
    
    def __init__(self, game_path: Path, mod_path: Path):
        self.game_path = game_path
        self.mod_path = mod_path
        self.logger = logging.getLogger('CK3ModManager')
        
        # Validation rules
        self.rules = {
            'events': {
                'required': ['namespace', 'id'],
                'optional': ['trigger', 'effect'],
                'patterns': {
                    'namespace': r'namespace\s*=\s*(\w+)',
                    'id': r'id\s*=\s*(\w+\.\d+)'
                }
            },
            'decisions': {
                'required': ['is_shown', 'effect'],
                'optional': ['ai_check'],
                'patterns': {
                    'is_shown': r'is_shown\s*=\s*{([^}]+)}',
                    'effect': r'effect\s*=\s*{([^}]+)}'
                }
            },
            'effects': {
                'valid': ['add_prestige', 'add_gold', 'trigger_event', 'add_trait'],
                'scopes': ['character', 'title', 'province']
            }
        }

    async def create_mod(self, mod_name: str, mod_info: Dict[str, Any]) -> bool:
        """Create a new mod with basic structure"""
        try:
            mod_path = self.mod_path / mod_name
            mod_path.mkdir(parents=True, exist_ok=True)

            # Create base folder structure
            folders = ['events', 'common/decisions', 'localization', 'gfx']
            for folder in folders:
                (mod_path / folder).mkdir(parents=True, exist_ok=True)

            # Create descriptor
            await self._create_descriptor(mod_path, mod_info)
            
            # Create base files
            await self._create_base_files(mod_path)

            self.logger.info(f"Created mod: {mod_name}")
            return True

        except Exception as e:
            self.logger.error(f"Error creating mod: {str(e)}")
            return False

    async def validate_mod(self, mod_name: str) -> ModValidation:
        """Validate mod structure and content"""
        try:
            mod_path = self.mod_path / mod_name
            if not mod_path.exists():
                return ModValidation(False, ["Mod not found"], [])

            errors = []
            warnings = []

            # Structure validation
            await self._validate_structure(mod_path, errors, warnings)
            
            # Content validation
            await self._validate_content(mod_path, errors, warnings)
            
            # Cross-reference validation
            await self._validate_references(mod_path, errors, warnings)

            return ModValidation(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return ModValidation(False, [str(e)], [])

    async def analyze_mod(self, mod_name: str) -> Dict[str, Any]:
        """Analyze mod content and structure"""
        try:
            mod_path = self.mod_path / mod_name
            
            analysis = {
                'events': await self._analyze_events(mod_path),
                'decisions': await self._analyze_decisions(mod_path),
                'references': await self._analyze_references(mod_path),
                'stats': await self._collect_stats(mod_path)
            }
            
            return analysis

        except Exception as e:
            self.logger.error(f"Analysis error: {str(e)}")
            return {'error': str(e)}

    async def _create_descriptor(self, mod_path: Path, mod_info: Dict[str, Any]):
        """Create mod descriptor file"""
        descriptor = {
            'name': mod_info.get('name', 'New Mod'),
            'version': mod_info.get('version', '1.0.0'),
            'supported_version': mod_info.get('supported_version', '1.8.*'),
            'path': str(mod_path),
            'tags': mod_info.get('tags', ['Historical', 'Gameplay'])
        }

        async with aiofiles.open(mod_path / 'descriptor.mod', 'w', encoding='utf-8') as f:
            for key, value in descriptor.items():
                if isinstance(value, list):
                    await f.write(f'{key}={{"' + '" "'.join(value) + '"}}\n')
                else:
                    await f.write(f'{key}="{value}"\n')

    async def _validate_structure(self, mod_path: Path, errors: List[str], warnings: List[str]):
        """Validate mod folder structure"""
        required_folders = ['events', 'common', 'localization']
        optional_folders = ['gfx', 'music', 'interface']
        
        for folder in required_folders:
            if not (mod_path / folder).exists():
                errors.append(f"Missing required folder: {folder}")
                
        for folder in optional_folders:
            if not (mod_path / folder).exists():
                warnings.append(f"Missing optional folder: {folder}")

    async def _validate_content(self, mod_path: Path, errors: List[str], warnings: List[str]):
        """Validate mod content files"""
        # Events validation
        event_files = list(mod_path.glob('events/**/*.txt'))
        for file in event_files:
            content = await self._read_file(file)
            await self._validate_events(content, file, errors, warnings)

        # Decisions validation
        decision_files = list(mod_path.glob('common/decisions/**/*.txt'))
        for file in decision_files:
            content = await self._read_file(file)
            await self._validate_decisions(content, file, errors, warnings)

    async def _validate_events(self, content: str, file_path: Path, errors: List[str], warnings: List[str]):
        """Validate event file content"""
        for pattern_name, pattern in self.rules['events']['patterns'].items():
            if not re.search(pattern, content):
                if pattern_name in self.rules['events']['required']:
                    errors.append(f"Missing required field '{pattern_name}' in {file_path}")
                else:
                    warnings.append(f"Missing optional field '{pattern_name}' in {file_path}")

    async def _analyze_references(self, mod_path: Path) -> Dict[str, Any]:
        """Analyze mod file references"""
        references = defaultdict(list)
        
        # Event references
        event_files = list(mod_path.glob('events/**/*.txt'))
        for file in event_files:
            content = await self._read_file(file)
            refs = self._extract_references(content)
            references['events'].extend(refs)
            
        return dict(references)

    async def _read_file(self, file_path: Path) -> str:
        """Read file content"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8-sig') as f:
            return await f.read()

    def _extract_references(self, content: str) -> List[Dict[str, str]]:
        """Extract references from content"""
        references = []
        # Event references
        event_refs = re.finditer(r'trigger_event\s*=\s*(\w+\.\d+)', content)
        for ref in event_refs:
            references.append({
                'type': 'event',
                'id': ref.group(1)
            })
        return references

    async def _collect_stats(self, mod_path: Path) -> Dict[str, int]:
        """Collect mod statistics"""
        return {
            'events': len(list(mod_path.glob('events/**/*.txt'))),
            'decisions': len(list(mod_path.glob('common/decisions/**/*.txt'))),
            'localizations': len(list(mod_path.glob('localization/**/*.yml')))
        }

# Usage example
async def main():
    # Initialize manager
    manager = CK3ModManager(
        game_path=Path("C:/Program Files (x86)/Steam/steamapps/common/Crusader Kings III"),
        mod_path=Path("Documents/Paradox Interactive/Crusader Kings III/mod")
    )

    # Create new mod
    mod_info = {
        'name': 'Test Mod',
        'version': '1.0.0',
        'supported_version': '1.8.*',
        'tags': ['Historical', 'Gameplay']
    }

    # Create and validate mod
    success = await manager.create_mod('test_mod', mod_info)
    if success:
        # Validate
        validation = await manager.validate_mod('test_mod')
        print(f"Validation: {validation}")
        
        # Analyze
        analysis = await manager.analyze_mod('test_mod')
        print(f"Analysis: {analysis}")

if __name__ == "__main__":
    asyncio.run(main())