/// The authenticated session: tokens + role + identity. Written to and
/// read from secure storage as a single JSON unit (see AuthStorage) — the
/// app never reads a role value that could have been separated from the
/// token it came from.
class AuthSession {
  final String accessToken;
  final String refreshToken;
  final String role;
  final String userId;
  final String username;

  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.role,
    required this.userId,
    required this.username,
  });

  bool get isHomeUser => role == 'HOME_USER';

  AuthSession copyWith({
    String? accessToken,
    String? refreshToken,
    String? role,
    String? userId,
    String? username,
  }) {
    return AuthSession(
      accessToken: accessToken ?? this.accessToken,
      refreshToken: refreshToken ?? this.refreshToken,
      role: role ?? this.role,
      userId: userId ?? this.userId,
      username: username ?? this.username,
    );
  }

  Map<String, dynamic> toJson() => {
        'access_token': accessToken,
        'refresh_token': refreshToken,
        'role': role,
        'user_id': userId,
        'username': username,
      };

  factory AuthSession.fromJson(Map<String, dynamic> json) => AuthSession(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
        role: json['role'] as String,
        userId: json['user_id'] as String,
        username: json['username'] as String,
      );
}
