import 'package:flutter_test/flutter_test.dart';

import 'package:kabadiwala_mobile/features/safety/safety_service.dart';

void main() {
  final service = SafetyService();

  test('returns smartphone safety guidance', () {
    final content = service.forCategory('Smartphone');

    expect(content.category, 'smartphone');
    expect(content.instructions, contains('Do not burn the device.'));
  });

  test('returns battery safety guidance', () {
    final content = service.forCategory('Batteries');

    expect(content.category, 'battery');
    expect(content.instructions, contains('Do not short-circuit the terminals.'));
  });

  test('returns PCB safety guidance', () {
    final content = service.forCategory('Circuit Board');

    expect(content.category, 'pcb');
    expect(content.instructions, contains('Do not burn the PCB.'));
  });

  test('returns generic guidance for unknown material', () {
    final content = service.forCategory('Unknown appliance');

    expect(content.category, 'generic-ewaste');
    expect(content.instructions, isNotEmpty);
  });

  test('matches category variations case and format tolerantly', () {
    expect(service.forCategory('smart phone').category, 'smartphone');
    expect(service.forCategory('MOBILE_PHONE').category, 'smartphone');
    expect(service.forCategory('hard-drive').category, 'hdd');
  });
}