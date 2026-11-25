"""Class guide (K18) on the web side: shell, notice, draft mark, scope, figures, a11y job."""
import json
import re
from pathlib import Path

import pytest
import yaml

from para_triage.education import scope as k2_scope
from para_triage.guide import scope

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SRC = WEB / "src"
GUIDE_SOURCES = [
    *sorted((SRC / "app" / "guia").glob("**/*.tsx")),
    *sorted((SRC / "components" / "guide").glob("*.tsx")),
    SRC / "lib" / "guide.ts",
    SRC / "lib" / "guide-types.ts",
    SRC / "components" / "site" / "site-nav.tsx",
]
SKIP_LINK = "Pular para o conteúdo"


def read(path):
    return path.read_text(encoding="utf-8")


def test_the_four_kinds_of_page_exist_and_all_render_through_the_guide_shell():
    pages = sorted(p.relative_to(SRC / "app").as_posix() for p in (SRC / "app" / "guia").glob("**/page.tsx"))
    assert pages == ["guia/[grupo]/[classe]/page.tsx", "guia/[grupo]/page.tsx", "guia/glossario/page.tsx", "guia/page.tsx"]
    for page in (SRC / "app" / "guia").glob("**/page.tsx"):
        assert "GuideShell" in read(page), page


def test_the_shell_shows_the_fixed_notice_the_draft_mark_the_version_and_the_trail():
    shell = read(SRC / "components" / "guide" / "guide-shell.tsx")
    assert "{guide.notice}" in shell and "rascunho até a especialista rever" in shell
    assert 'status === "reviewed" ? "Revisado" : "Rascunho"' in shell and "<DraftBadge" in shell
    assert "guide.rules_id" in shell and "guide.generated_on" in shell and "guide.rules_path" in shell
    assert 'aria-label="Trilha"' in shell and 'aria-current="page"' in shell
    assert 'id="conteudo"' in shell and "<Freshness" in shell
    content = json.loads(read(SRC / "content" / "guide.json"))
    assert content["notice"] == scope.NOTICE


def test_every_main_is_the_skip_target_and_the_skip_link_exists_only_in_the_shell():
    mains = [(path, text) for path in SRC.glob("**/*.tsx") if "<main" in (text := read(path))]
    assert len(mains) >= 4
    for path, text in mains:
        assert text.count("<main") == text.count('<main id="conteudo"'), path
    with_link = [p.relative_to(SRC).as_posix() for p in SRC.glob("**/*.tsx") if SKIP_LINK in read(p)]
    assert with_link == ["components/site/site-nav.tsx"]


def test_the_navigation_is_in_the_root_layout_with_four_plain_links():
    layout = read(SRC / "app" / "layout.tsx")
    assert "<SiteNav />" in layout and layout.index("<SiteNav />") < layout.index("{children}")
    nav = read(SRC / "components" / "site" / "site-nav.tsx")
    assert 'aria-label="Principal"' in nav and "aria-current" in nav and "print:hidden" in nav
    assert re.findall(r'href: "([^"]+)"', nav) == ["/", "/educacao", "/guia", "/transparencia"]
    for forbidden in ("onMouseEnter", "onMouseOver", "aria-haspopup", "aria-expanded"):
        assert forbidden not in nav


@pytest.mark.parametrize("path", GUIDE_SOURCES, ids=lambda p: p.name)
def test_guide_code_has_no_hover_only_content_storage_images_or_outside_groups(path):
    text = read(path)
    for forbidden in ("onMouseEnter", "onMouseOver", "onMouseLeave", "group-hover:block", "group-hover:visible"):
        assert forbidden not in text, (path.name, forbidden)
    for storage in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
        assert storage not in text, (path.name, storage)
    assert "<img" not in text and "next/image" not in text and "https://" not in text and "http://" not in text
    for group in k2_scope.EXCLUDED_GROUPS:
        assert group not in text, (path.name, group)
    assert "acurácia" not in text.lower() and "accuracy" not in text.lower()


def test_figures_use_only_the_text_colour_patterns_and_labels_of_at_least_the_minimum_size():
    figures = read(SRC / "components" / "guide" / "figures.tsx")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", figures)
    assert not re.search(r"\b(rgb|rgba|hsl|hsla|oklch|oklab)\(", figures)
    assert "currentColor" in figures and 'role="img"' in figures
    assert "aria-labelledby" in figures and "aria-describedby" in figures and "<title" in figures and "<desc" in figures
    assert int(re.search(r"const FONT = (\d+);", figures).group(1)) >= 12
    assert "Descrição da figura" in figures and "<figcaption" in figures


def test_glossary_terms_are_links_to_the_glossary_page_not_popups():
    rich = read(SRC / "components" / "guide" / "rich.tsx")
    assert "guide.glossary_path" in rich and "<Link" in rich
    glossary = read(SRC / "app" / "guia" / "glossario" / "page.tsx")
    assert "<dl" in glossary and "id={item.id}" in glossary


def test_the_runtime_freshness_check_never_blocks_the_page():
    freshness = read(SRC / "components" / "guide" / "freshness.tsx")
    assert "shouldRetryOnError: false" in freshness and 'role="status"' in freshness
    assert "throw" not in freshness and "error" not in freshness.lower().replace("shouldretryonerror", "")


# --- the accessibility job -------------------------------------------------------------------------------------------


def test_the_a11y_job_pins_versions_installs_without_saving_and_tells_infra_from_violations():
    workflow = yaml.safe_load(read(ROOT / ".github" / "workflows" / "ci.yml"))
    job = workflow["jobs"]["a11y"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", job["env"]["PLAYWRIGHT_VERSION"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", job["env"]["AXE_PLAYWRIGHT_VERSION"])
    text = read(ROOT / ".github" / "workflows" / "ci.yml")
    assert "--no-save" in text and "actions/cache@v4" in text and "ms-playwright" in text
    assert 'name: "INFRA: install Chromium"' in text and 'name: "A11Y:' in text
    package = json.loads(read(WEB / "package.json"))
    declared = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    assert not any("playwright" in name or "axe" in name for name in declared)  # not saved


def test_the_a11y_script_separates_exit_codes_and_covers_every_guide_page_and_both_widths():
    script = read(WEB / "scripts" / "a11y.mjs")
    assert "process.exit(2)" in script and "process.exit(1)" in script and "INFRA:" in script and "A11Y:" in script
    assert "wcag22aa" in script and "width: 320" in script and "width: 1280" in script
    assert "guide.pages.map" in script and '"/transparencia"' in script
