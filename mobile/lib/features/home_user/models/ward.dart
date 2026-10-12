class Ward {
  final String wardId;
  final String name;

  const Ward({required this.wardId, required this.name});

  factory Ward.fromJson(Map<String, dynamic> json) => Ward(
        wardId: json['ward_id'] as String,
        name: json['name'] as String,
      );
}
