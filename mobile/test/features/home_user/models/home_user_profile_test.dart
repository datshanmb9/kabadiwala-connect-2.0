import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/home_user/models/home_user_profile.dart';
import 'package:kabadiwala_mobile/features/home_user/models/ward.dart';

void main() {
  test('HomeUserProfile.fromJson parses the exact backend response shape', () {
    final profile = HomeUserProfile.fromJson({
      'user_id': 'user-1',
      'username': 'citizen1',
      'full_name': 'Citizen One',
      'address': '1 Main St',
      'ward_id': 'WARD-1',
      'household_lat': 12.9716,
      'household_lng': 77.5946,
      'upi_id': 'citizen1@upi',
    });
    expect(profile.userId, 'user-1');
    expect(profile.householdLat, 12.9716);
    expect(profile.upiId, 'citizen1@upi');
  });

  test('HomeUserProfile.fromJson handles a null upi_id', () {
    final profile = HomeUserProfile.fromJson({
      'user_id': 'user-1',
      'username': 'citizen1',
      'full_name': 'Citizen One',
      'address': '1 Main St',
      'ward_id': 'WARD-1',
      'household_lat': 12.9716,
      'household_lng': 77.5946,
      'upi_id': null,
    });
    expect(profile.upiId, isNull);
  });

  test('Ward.fromJson parses ward_id and name', () {
    final ward = Ward.fromJson({'ward_id': 'WARD-1', 'name': 'Test Ward 1'});
    expect(ward.wardId, 'WARD-1');
    expect(ward.name, 'Test Ward 1');
  });
}
