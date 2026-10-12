import 'models/safety_content.dart';

class SafetyService {
  static const _language = 'en';

  static const _generic = SafetyContent(
    category: 'generic-ewaste',
    language: _language,
    title: 'Safe e-waste handling',
    instructions: [
      'Do not burn, crush, or puncture the item.',
      'Keep damaged items away from heat, flames, children, and pets.',
      'Handle sharp, broken, or leaking parts carefully.',
      'Keep the item dry and hand it over for safe collection.',
    ],
  );

  static const _content = <String, SafetyContent>{
    'smartphone': SafetyContent(
      category: 'smartphone',
      language: _language,
      title: 'Smartphone safety',
      instructions: [
        'Do not burn the device.',
        'Do not puncture or crush the battery.',
        'Keep damaged batteries away from heat and flames.',
        'Handle damaged devices carefully.',
      ],
    ),
    'battery': SafetyContent(
      category: 'battery',
      language: _language,
      title: 'Battery safety',
      instructions: [
        'Do not puncture, crush, or burn the battery.',
        'Keep it away from heat and flames.',
        'Do not short-circuit the terminals.',
        'Handle damaged or swollen batteries carefully.',
      ],
    ),
    'pcb': SafetyContent(
      category: 'pcb',
      language: _language,
      title: 'PCB safety',
      instructions: [
        'Do not burn the PCB.',
        'Do not perform unsafe chemical extraction.',
        'Avoid direct contact with damaged components.',
        'Use appropriate protective equipment when handling it.',
      ],
    ),
    'cable': SafetyContent(
      category: 'cable',
      language: _language,
      title: 'Cable safety',
      instructions: [
        'Do not open-air burn cables.',
        'Do not strip cables using unsafe methods.',
        'Keep damaged cables away from electrical sources.',
        'Handle exposed or sharp wire ends carefully.',
      ],
    ),
    'laptop': SafetyContent(
      category: 'laptop',
      language: _language,
      title: 'Laptop safety',
      instructions: [
        'Do not burn or dismantle the laptop unnecessarily.',
        'Handle the battery carefully.',
        'Do not puncture or crush the battery.',
        'Keep damaged batteries away from heat.',
      ],
    ),
    'tv-crt': SafetyContent(
      category: 'tv-crt',
      language: _language,
      title: 'TV/CRT safety',
      instructions: [
        'Do not break the screen.',
        'Handle glass carefully.',
        'Do not burn the device.',
        'Keep damaged CRT or display components away from people.',
      ],
    ),
    'hdd': SafetyContent(
      category: 'hdd',
      language: _language,
      title: 'HDD safety',
      instructions: [
        'Handle damaged or sharp components carefully.',
        'Do not burn the HDD.',
        'Do not dismantle it unnecessarily.',
        'Keep damaged parts contained for collection.',
      ],
    ),
  };

  static const _aliases = <String, List<String>>{
    'smartphone': ['smartphone', 'smart phone', 'mobile', 'mobile phone', 'cell phone', 'phone'],
    'battery': ['battery', 'batteries', 'cell'],
    'pcb': ['pcb', 'circuit board', 'circuit-board'],
    'cable': ['cable', 'wire', 'wires'],
    'laptop': ['laptop', 'notebook computer'],
    'tv-crt': ['tv', 'television', 'crt', 'display'],
    'hdd': ['hdd', 'hard disk', 'hard drive'],
  };

  SafetyContent forCategory(String? category) {
    final normalized = _normalize(category);
    // A detected "TV Remote Control" contains "tv" but has no screen/CRT;
    // it gets the general e-waste guidance, not TV/CRT instructions.
    if (normalized.contains('remote')) return _generic;
    for (final entry in _aliases.entries) {
      if (entry.value.any(normalized.contains)) {
        return _content[entry.key]!;
      }
    }
    return _generic;
  }

  String _normalize(String? value) => (value ?? '')
      .trim()
      .toLowerCase()
      .replaceAll(RegExp(r'[_/\-]+'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ');
}