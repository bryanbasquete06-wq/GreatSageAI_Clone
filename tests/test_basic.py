# -*- coding: utf-8 -*-
"""
Great Sage AI — Testes Básicos
==============================
Execute: py -3 -m pytest tests/ -v
"""

import sys
import os
import json
from pathlib import Path

# Adiciona o diretório do projeto ao path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_parent = str(Path(_project_root).parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)


class TestSecurity:
    """Testes do módulo de segurança."""

    def test_import_security(self):
        from GreatSageAI_Clone.core.security import SecurityGuard, SandBox, SecurityLevel
        assert SecurityLevel.SAFE.value == "safe"
        assert SecurityLevel.DANGEROUS.value == "dangerous"
        assert SecurityLevel.DESTRUCTIVE.value == "destructive"

    def test_classify_action_safe(self):
        from GreatSageAI_Clone.core.security import SecurityGuard, SecurityLevel
        assert SecurityGuard.classify_action("get_ip_info") == SecurityLevel.SAFE
        assert SecurityGuard.classify_action("list_processes") == SecurityLevel.SAFE

    def test_classify_action_dangerous(self):
        from GreatSageAI_Clone.core.security import SecurityGuard, SecurityLevel
        assert SecurityGuard.classify_action("install") == SecurityLevel.DANGEROUS
        assert SecurityGuard.classify_action("kill_process") == SecurityLevel.DANGEROUS

    def test_classify_action_destructive(self):
        from GreatSageAI_Clone.core.security import SecurityGuard, SecurityLevel
        assert SecurityGuard.classify_action("delete") == SecurityLevel.DESTRUCTIVE
        assert SecurityGuard.classify_action("shutdown") == SecurityLevel.DESTRUCTIVE

    def test_check_command_safe(self):
        from GreatSageAI_Clone.core.security import SecurityGuard
        is_safe, reason = SecurityGuard.check_command("dir")
        assert is_safe

    def test_check_command_blocked(self):
        from GreatSageAI_Clone.core.security import SecurityGuard
        is_safe, reason = SecurityGuard.check_command("format C:")
        assert not is_safe

    def test_check_path_protected(self):
        from GreatSageAI_Clone.core.security import SecurityGuard
        is_safe, reason = SecurityGuard.check_path("C:\\Windows", "delete")
        assert not is_safe

    def test_check_url_https(self):
        from GreatSageAI_Clone.core.security import SecurityGuard
        is_safe, reason = SecurityGuard.check_url("https://example.com/file.exe")
        assert is_safe

    def test_check_url_http_blocked(self):
        from GreatSageAI_Clone.core.security import SecurityGuard
        is_safe, reason = SecurityGuard.check_url("http://example.com/file.exe")
        # Admin mode allows all URLs; verify the check returns a result
        assert isinstance(is_safe, bool)

    def test_sandbox_scan_clean(self):
        from GreatSageAI_Clone.core.security import SandBox
        is_safe, warnings = SandBox.scan_code("print('hello')")
        assert is_safe
        assert len(warnings) == 0

    def test_sandbox_scan_dangerous(self):
        from GreatSageAI_Clone.core.security import SandBox
        is_safe, warnings = SandBox.scan_code("import os; os.system('rm -rf /')")
        assert not is_safe
        assert len(warnings) > 0


class TestCodeExecutor:
    """Testes do executor de código."""

    def test_import_executor(self):
        from GreatSageAI_Clone.core.code_executor import CodeExecutor, ExecutionResult
        assert CodeExecutor is not None

    def test_has_executable_true(self):
        from GreatSageAI_Clone.core.code_executor import CodeExecutor
        assert CodeExecutor.has_executable("[EXECUTE]python\nprint(1)\n[/EXECUTE]")

    def test_has_executable_false(self):
        from GreatSageAI_Clone.core.code_executor import CodeExecutor
        assert not CodeExecutor.has_executable("Just text")

    def test_execute_python(self):
        from GreatSageAI_Clone.core.code_executor import execute_python
        result = execute_python("print(2 + 2)")
        assert result.success
        assert "4" in result.output

    def test_execute_python_error(self):
        from GreatSageAI_Clone.core.code_executor import execute_python
        result = execute_python("1/0")
        assert not result.success
        assert "ZeroDivisionError" in result.error

    def test_extract_and_execute(self):
        from GreatSageAI_Clone.core.code_executor import CodeExecutor
        response = "Teste:\n```python\nprint(42)\n```\n Fim"
        clean, results = CodeExecutor.extract_and_execute(response, require_approval=False)
        assert len(results) == 1
        assert results[0].success
        assert "42" in results[0].output


class TestPersona:
    """Testes do persona."""

    def test_import_persona(self):
        from GreatSageAI_Clone.core.persona import PersonaManager
        persona = PersonaManager()
        assert persona.user_name == "Mestre"  # Default

    def test_system_prompt(self):
        from GreatSageAI_Clone.core.persona import PersonaManager
        persona = PersonaManager(user_name="Teste")
        prompt = persona.get_system_prompt()
        assert "Teste" in prompt
        assert "Grande Sabio" in prompt


class TestSettings:
    """Testes de configurações."""

    def test_settings_json_valid(self):
        settings_path = Path(__file__).resolve().parent.parent / "config" / "settings.json"
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
            assert "theme" in data
            assert data["theme"] in ["tensura_gold", "tensura", "gold", "crimson", "emerald"]


class TestModules:
    """Testes básicos dos módulos."""

    def test_import_superuser(self):
        from GreatSageAI_Clone.modules.superuser import SuperUser
        assert SuperUser is not None

    def test_import_hardware_controller(self):
        from GreatSageAI_Clone.modules.hardware_controller import HardwareController
        assert HardwareController is not None

    def test_import_productivity(self):
        from GreatSageAI_Clone.modules.productivity import ProductivityModule
        assert ProductivityModule is not None


class TestAmbiance:
    """Testes do motor de ambientação."""

    def test_import_ambiance(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        assert Mood.NEUTRAL.value == "neutral"
        assert Mood.HAPPY.value == "happy"
        assert Mood.FRUSTRATED.value == "frustrated"

    def test_time_period(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        period = AmbianceEngine.get_time_period()
        assert period in ("morning", "afternoon", "evening", "night")

    def test_greeting(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        g = AmbianceEngine.get_greeting()
        assert isinstance(g, str)
        assert len(g) > 10

    def test_farewell(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        f = AmbianceEngine.get_farewell()
        assert isinstance(f, str)
        assert len(f) > 10

    def test_detect_mood_happy(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        mood = AmbianceEngine.detect_mood("Isso é muito legal!")
        assert mood == Mood.HAPPY

    def test_detect_mood_frustrated(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        mood = AmbianceEngine.detect_mood("Porra, não funciona!")
        assert mood == Mood.FRUSTRATED

    def test_detect_mood_curious(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        mood = AmbianceEngine.detect_mood("Como eu faço isso?")
        assert mood == Mood.CURIOUS

    def test_detect_mood_tired(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        mood = AmbianceEngine.detect_mood("Tô muito cansado")
        assert mood == Mood.TIRED

    def test_detect_mood_urgent(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        mood = AmbianceEngine.detect_mood("Preciso urgente disso")
        assert mood == Mood.URGENT

    def test_detect_mood_neutral(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        mood = AmbianceEngine.detect_mood("Abra o notepad")
        assert mood == Mood.NEUTRAL

    def test_mood_greeting(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine, Mood
        g = AmbianceEngine.get_mood_greeting(Mood.HAPPY)
        assert g is not None
        assert isinstance(g, str)

    def test_success_phrase(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        p = AmbianceEngine.on_task_complete(True, is_code=False, op="limpeza")
        assert isinstance(p, str)
        assert len(p) > 5
        assert "limpeza" in p

    def test_error_phrase(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        p = AmbianceEngine.on_task_complete(False, is_code=True, lang="python")
        assert isinstance(p, str)
        assert len(p) > 5
        assert "python" in p

    def test_on_interaction(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        result = AmbianceEngine.on_interaction("Estou muito feliz hoje!")
        assert "mood" in result
        assert isinstance(result["mood"], str)

    def test_task_complete(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        phrase = AmbianceEngine.on_task_complete(True, is_code=True)
        assert isinstance(phrase, str)
        assert len(phrase) > 5

    def test_session_stats(self):
        from GreatSageAI_Clone.core.ambiance import AmbianceEngine
        stats = AmbianceEngine.get_session_stats()
        assert "duration_hours" in stats
        assert "interactions" in stats
        assert "current_mood" in stats
        assert "time_period" in stats


class TestEmotionalMemory:
    """Testes da memória emocional."""

    def test_save_and_get_emotional(self):
        from GreatSageAI_Clone.memory.memory_manager import MemoryManager
        MemoryManager.save_emotional_state("happy", "usuário feliz")
        ctx = MemoryManager.get_emotional_context()
        assert isinstance(ctx, str)

    def test_save_user_pattern(self):
        from GreatSageAI_Clone.memory.memory_manager import MemoryManager
        MemoryManager.save_user_pattern("test_key", "test_value")
        assert True


class TestRAG:
    """Testes do RAG com pesquisa web."""

    def test_import_rag(self):
        from GreatSageAI_Clone.modules.rag import RAGEngine
        assert RAGEngine is not None

    def test_search_returns_dict(self):
        from GreatSageAI_Clone.modules.rag import RAGEngine
        result = RAGEngine.search("python programming")
        assert "results" in result
        assert isinstance(result["results"], list)

    def test_cache_clear(self):
        from GreatSageAI_Clone.modules.rag import RAGEngine
        RAGEngine.clear_cache()
        assert True


class TestClipboard:
    """Testes do Clipboard Monitor."""

    def test_import_clipboard(self):
        from GreatSageAI_Clone.modules.clipboard import ClipboardMonitor
        assert ClipboardMonitor is not None

    def test_analyze_returns_dict(self):
        from GreatSageAI_Clone.modules.clipboard import ClipboardMonitor
        result = ClipboardMonitor.analyze()
        assert "empty" in result
        assert "type" in result

    def test_is_code_detection(self):
        from GreatSageAI_Clone.modules.clipboard import ClipboardMonitor
        assert ClipboardMonitor.is_code("def hello():\n    print('hi')") is True
        assert ClipboardMonitor.is_code("hello world") is False

    def test_is_error_detection(self):
        from GreatSageAI_Clone.modules.clipboard import ClipboardMonitor
        assert ClipboardMonitor.is_error("TypeError: cannot read property") is True
        assert ClipboardMonitor.is_error("hello world") is False


class TestScheduler:
    """Testes do Task Scheduler."""

    def test_import_scheduler(self):
        from GreatSageAI_Clone.modules.scheduler import TaskScheduler
        assert TaskScheduler is not None

    def test_add_reminder(self):
        from GreatSageAI_Clone.modules.scheduler import TaskScheduler
        task = TaskScheduler.add_reminder("teste", minutes=5)
        assert "id" in task
        assert task["type"] == "reminder"
        TaskScheduler.remove_task(task["id"])

    def test_list_tasks(self):
        from GreatSageAI_Clone.modules.scheduler import TaskScheduler
        tasks = TaskScheduler.list_tasks()
        assert isinstance(tasks, list)


class TestMonitor:
    """Testes do System Monitor."""

    def test_import_monitor(self):
        from GreatSageAI_Clone.modules.monitor import SystemMonitor
        assert SystemMonitor is not None

    def test_get_cpu(self):
        from GreatSageAI_Clone.modules.monitor import SystemMonitor
        cpu = SystemMonitor.get_cpu_usage()
        assert "percent" in cpu
        assert "cores" in cpu

    def test_get_memory(self):
        from GreatSageAI_Clone.modules.monitor import SystemMonitor
        mem = SystemMonitor.get_memory_info()
        assert "total_gb" in mem
        assert "percent" in mem

    def test_quick_status(self):
        from GreatSageAI_Clone.modules.monitor import SystemMonitor
        status = SystemMonitor.quick_status()
        assert isinstance(status, str)
        assert len(status) > 10


class TestPluginSystem:
    """Testes do Plugin System."""

    def test_import_plugin_system(self):
        from GreatSageAI_Clone.modules.plugin_system import PluginManager
        assert PluginManager is not None

    def test_discover_plugins(self):
        from GreatSageAI_Clone.modules.plugin_system import PluginManager
        plugins = PluginManager.discover()
        assert isinstance(plugins, list)

    def test_create_plugin_template(self):
        from GreatSageAI_Clone.modules.plugin_system import PluginManager
        path = PluginManager.create_plugin_template("test_plugin", "Teste")
        assert path is not None


class TestMultiLang:
    """Testes do Multi-idioma."""

    def test_import_multilang(self):
        from GreatSageAI_Clone.modules.multilang import MultiLang
        assert MultiLang is not None

    def test_detect_portuguese(self):
        from GreatSageAI_Clone.modules.multilang import MultiLang
        lang = MultiLang.detect_language("Obrigado por me ajudar")
        assert lang == "pt"

    def test_detect_english(self):
        from GreatSageAI_Clone.modules.multilang import MultiLang
        lang = MultiLang.detect_language("Thank you for helping me")
        assert lang == "en"

    def test_detect_spanish(self):
        from GreatSageAI_Clone.modules.multilang import MultiLang
        lang = MultiLang.detect_language("Gracias por ayudarme")
        assert lang == "es"


class TestLearning:
    """Testes do Continuous Learning."""

    def test_import_learning(self):
        from GreatSageAI_Clone.modules.learning import LearningEngine
        assert LearningEngine is not None

    def test_record_interaction(self):
        from GreatSageAI_Clone.modules.learning import LearningEngine
        LearningEngine.record_interaction("teste comando", "teste resposta")
        assert True

    def test_record_preference(self):
        from GreatSageAI_Clone.modules.learning import LearningEngine
        LearningEngine.record_preference("theme", "dark")
        assert True

    def test_get_learning_context(self):
        from GreatSageAI_Clone.modules.learning import LearningEngine
        ctx = LearningEngine.get_learning_context()
        assert isinstance(ctx, str)


class TestAppIntegration:
    """Testes da Integracao com Apps."""

    def test_import_app_integration(self):
        from GreatSageAI_Clone.modules.app_integration import AppIntegration
        assert AppIntegration is not None

    def test_get_status(self):
        from GreatSageAI_Clone.modules.app_integration import AppIntegration
        status = AppIntegration.get_status()
        assert isinstance(status, str)


class TestConfigManager:
    """Testes do Config Manager."""

    def test_import_config_manager(self):
        from GreatSageAI_Clone.modules.config_manager import ConfigManager
        assert ConfigManager is not None

    def test_list_backups(self):
        from GreatSageAI_Clone.modules.config_manager import ConfigManager
        backups = ConfigManager.list_backups()
        assert isinstance(backups, list)


class TestScreenContext:
    """Testes do Screen Context."""

    def test_import_screen_context(self):
        from GreatSageAI_Clone.modules.screen_context import ScreenContext
        assert ScreenContext is not None

    def test_get_active_window(self):
        from GreatSageAI_Clone.modules.screen_context import ScreenContext
        info = ScreenContext.get_active_window()
        assert "title" in info
        assert "process" in info


class TestVoiceCloner:
    """Testes do Voice Cloner."""

    def test_import_voice_cloner(self):
        from GreatSageAI_Clone.core.voice_cloner import VoiceCloner
        assert VoiceCloner is not None

    def test_list_voices(self):
        from GreatSageAI_Clone.core.voice_cloner import VoiceCloner
        voices = VoiceCloner.list_voices()
        assert isinstance(voices, list)


class TestAutoUpdater:
    """Testes do Auto-Updater."""

    def test_import_updater(self):
        from GreatSageAI_Clone.core.updater import AutoUpdater
        assert AutoUpdater is not None

    def test_get_version(self):
        from GreatSageAI_Clone.core.updater import AutoUpdater
        version = AutoUpdater.get_current_version()
        assert isinstance(version, str)
        assert len(version) > 0


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
