import sys
import os

# Add the project root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

from src.data.referee_source_mapper import RefereeSourceMapper, LaLigaRefereeScraper, PremierLeagueRefereeScraper, InternationalRefereePoolScraper

def test_mapping():
    test_cases = [
        ("La Liga", LaLigaRefereeScraper),
        ("La Liga EA Sports", LaLigaRefereeScraper),
        ("La Liga (España)", LaLigaRefereeScraper),
        ("Primera Division", LaLigaRefereeScraper),
        ("Premier League", PremierLeagueRefereeScraper),
        ("Premier League (Inglaterra)", PremierLeagueRefereeScraper),
        ("EPL", InternationalRefereePoolScraper), # Not explicitly handled yet, falls back to International
        ("Champions League", InternationalRefereePoolScraper),
        ("Liga Mixta (Combinada)", InternationalRefereePoolScraper),
    ]

    print("--- Testing Referee Mapping ---")
    all_passed = True
    for league_name, expected_class in test_cases:
        scraper = RefereeSourceMapper.get_scraper(league_name)
        passed = isinstance(scraper, expected_class)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}]: '{league_name}' -> {scraper.__class__.__name__} (Expected: {expected_class.__name__})")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nALL MAPPING TESTS PASSED")
    else:
        print("\nSOME MAPPING TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    test_mapping()
