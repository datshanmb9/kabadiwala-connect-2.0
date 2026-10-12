import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/collector/models/collector_profile.dart';

void main() {
  test('CollectorProfile.fromJson parses the full backend response shape', () {
    final profile = CollectorProfile.fromJson({
      'user_id': 'coll-1',
      'employee_id': 'EMP-001',
      'ward_id': 'WARD-1',
      'rrr_id': 'RRR-1',
      'assigned_area_radius_m': 500.0,
    });
    expect(profile.userId, 'coll-1');
    expect(profile.employeeId, 'EMP-001');
    expect(profile.wardId, 'WARD-1');
    expect(profile.rrrId, 'RRR-1');
    expect(profile.assignedAreaRadiusM, 500.0);
  });

  test('CollectorProfile.fromJson handles null rrr_id and assigned_area_radius_m', () {
    final profile = CollectorProfile.fromJson({
      'user_id': 'coll-1',
      'employee_id': 'EMP-001',
      'ward_id': 'WARD-1',
      'rrr_id': null,
      'assigned_area_radius_m': null,
    });
    expect(profile.rrrId, isNull);
    expect(profile.assignedAreaRadiusM, isNull);
  });
}
