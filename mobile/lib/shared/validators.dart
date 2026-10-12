/// Pure, framework-light form validators — return null when valid, an
/// error string otherwise, so they're usable both from TextFormField's
/// `validator` and from plain unit tests.
class Validators {
  static String? required(String? value, {String field = 'This field'}) {
    if (value == null || value.trim().isEmpty) return '$field is required';
    return null;
  }

  static String? username(String? value) {
    final req = required(value, field: 'Username');
    if (req != null) return req;
    if (value!.trim().length < 3) return 'Username must be at least 3 characters';
    return null;
  }

  static String? password(String? value) {
    final req = required(value, field: 'Password');
    if (req != null) return req;
    if (value!.length < 6) return 'Password must be at least 6 characters';
    return null;
  }

  static String? fullName(String? value) => required(value, field: 'Full name');

  static String? address(String? value) => required(value, field: 'Address');

  static String? ward(String? value) => required(value, field: 'Ward');

  static String? latitude(double? value) {
    if (value == null) return 'Location is required — tap "Use current location"';
    if (value < -90 || value > 90) return 'Invalid latitude';
    return null;
  }

  static String? longitude(double? value) {
    if (value == null) return 'Location is required — tap "Use current location"';
    if (value < -180 || value > 180) return 'Invalid longitude';
    return null;
  }
}
