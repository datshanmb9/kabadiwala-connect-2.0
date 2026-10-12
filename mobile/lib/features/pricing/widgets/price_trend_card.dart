import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../auth/auth_controller.dart';
import '../../ewaste/ewaste_repository.dart';
import '../../translation/translation_text.dart';
import '../price_trend.dart';

String _date(DateTime d) => '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}';

({String label, IconData icon, Color color}) _trendStyle(String trend) => switch (trend) {
      'increasing' => (label: 'Increasing', icon: Icons.trending_up, color: Colors.green.shade700),
      'decreasing' => (label: 'Decreasing', icon: Icons.trending_down, color: Colors.red.shade700),
      _ => (label: 'Stable', icon: Icons.trending_flat, color: Colors.blueGrey.shade600),
    };

Future<PriceTrend> fetchPriceTrend(BuildContext context, {required String item, String? wardId}) {
  final token = context.read<AuthController>().session?.accessToken;
  if (token == null) return Future.error(StateError('Not logged in'));
  return context.read<EwasteRepository>().getPriceTrend(accessToken: token, item: item, wardId: wardId);
}

/// "Price Trend" card for an item: real historical INR/kg from the backend
/// as a line chart, the direction and the latest observed price — or a
/// "not enough historical data" state. Used by Home User and Collector.
class PriceTrendCard extends StatefulWidget {
  final String item;
  final String? wardId;

  const PriceTrendCard({super.key, required this.item, this.wardId});

  @override
  State<PriceTrendCard> createState() => _PriceTrendCardState();
}

class _PriceTrendCardState extends State<PriceTrendCard> {
  late Future<PriceTrend> _future;

  @override
  void initState() {
    super.initState();
    _future = fetchPriceTrend(context, item: widget.item, wardId: widget.wardId);
  }

  @override
  void didUpdateWidget(PriceTrendCard old) {
    super.didUpdateWidget(old);
    if (old.item != widget.item || old.wardId != widget.wardId) {
      _future = fetchPriceTrend(context, item: widget.item, wardId: widget.wardId);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('price_trend_card'),
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FutureBuilder<PriceTrend>(
          future: _future,
          builder: (context, snapshot) {
            final title = Text(context.tr('Price Trend'), style: Theme.of(context).textTheme.titleMedium);
            if (snapshot.connectionState != ConnectionState.done) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [title, const SizedBox(height: 12), const LinearProgressIndicator()],
              );
            }
            if (snapshot.hasError) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  title,
                  const SizedBox(height: 8),
                  Text(context.tr('Price trend is unavailable right now.'), style: const TextStyle(color: Colors.grey)),
                ],
              );
            }
            final trend = snapshot.data!;
            if (!trend.hasTrend) return _NotEnoughData(title: title);
            return _TrendContent(title: title, trend: trend);
          },
        ),
      ),
    );
  }
}

class _NotEnoughData extends StatelessWidget {
  final Widget title;
  const _NotEnoughData({required this.title});

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const Key('price_trend_insufficient'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        title,
        const SizedBox(height: 12),
        Row(
          children: [
            Icon(Icons.show_chart, color: Colors.grey.shade400),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                context.tr('Not enough historical data yet.'),
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          context.tr('Trend will appear as more market price data is collected.'),
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
        ),
      ],
    );
  }
}

class _TrendContent extends StatelessWidget {
  final Widget title;
  final PriceTrend trend;
  const _TrendContent({required this.title, required this.trend});

  @override
  Widget build(BuildContext context) {
    final style = _trendStyle(trend.trend);
    final where = trend.scope == 'ward' && trend.wardId != null
        ? '${context.tr('Ward')} ${trend.wardId}'
        : context.tr('All wards');
    final change = trend.changePercent == null
        ? ''
        : ' (${trend.changePercent! >= 0 ? '+' : ''}${trend.changePercent!.toStringAsFixed(1)}%)';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: title),
            Chip(
              key: const Key('price_trend_direction'),
              avatar: Icon(style.icon, size: 18, color: style.color),
              label: Text(context.tr(style.label), style: TextStyle(color: style.color, fontWeight: FontWeight.w600)),
              visualDensity: VisualDensity.compact,
            ),
          ],
        ),
        Text(
          '${trend.item} · $where · ${context.trf('Last {days} days', {'days': trend.windowDays})}',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 170,
          width: double.infinity,
          child: CustomPaint(
            key: const Key('price_trend_chart'),
            painter: PriceTrendChartPainter(points: trend.points, color: style.color),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          '${context.tr('Trend:')} ${context.tr(style.label)}$change',
          style: TextStyle(color: style.color, fontWeight: FontWeight.w600),
        ),
        if (trend.latestPricePerKg != null)
          Text(
            '${context.tr('Latest market price:')} ₹${trend.latestPricePerKg!.toStringAsFixed(2)}/kg'
            '${trend.latestDate == null ? '' : ' (${_date(trend.latestDate!)})'}',
          ),
        const SizedBox(height: 6),
        Text(
          context.trf('Based on {count} accepted recycler bids on Kabadiwala Connect.', {'count': trend.totalSales}),
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade600),
        ),
      ],
    );
  }
}

/// Line chart of price/kg over time. X is proportional to the actual dates
/// (gaps between observations are not hidden); Y spans the observed range.
class PriceTrendChartPainter extends CustomPainter {
  final List<PriceTrendPoint> points;
  final Color color;

  PriceTrendChartPainter({required this.points, required this.color});

  static const _leftAxis = 52.0;
  static const _bottomAxis = 22.0;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    final chart = Rect.fromLTRB(_leftAxis, 8, size.width - 8, size.height - _bottomAxis);

    final prices = points.map((p) => p.pricePerKg);
    var minY = prices.reduce((a, b) => a < b ? a : b);
    var maxY = prices.reduce((a, b) => a > b ? a : b);
    final pad = (maxY - minY) == 0 ? (maxY.abs() * 0.1 + 1) : (maxY - minY) * 0.12;
    minY -= pad;
    maxY += pad;
    final start = points.first.date.millisecondsSinceEpoch.toDouble();
    final span = (points.last.date.millisecondsSinceEpoch - start).toDouble();

    Offset at(PriceTrendPoint p) => Offset(
          chart.left + (span == 0 ? 0 : (p.date.millisecondsSinceEpoch - start) / span) * chart.width,
          chart.bottom - (p.pricePerKg - minY) / (maxY - minY) * chart.height,
        );

    // Grid + Y labels (₹/kg).
    final grid = Paint()
      ..color = Colors.grey.shade300
      ..strokeWidth = 1;
    for (var i = 0; i <= 3; i++) {
      final y = chart.top + chart.height * i / 3;
      canvas.drawLine(Offset(chart.left, y), Offset(chart.right, y), grid);
      final value = maxY - (maxY - minY) * i / 3;
      _label(canvas, '₹${value.toStringAsFixed(0)}', Offset(0, y - 7), width: _leftAxis - 6, alignRight: true);
    }

    // X labels: first and last observation dates.
    _label(canvas, _date(points.first.date), Offset(chart.left, chart.bottom + 5));
    _label(canvas, _date(points.last.date), Offset(chart.right - 36, chart.bottom + 5), width: 36, alignRight: true);

    // Area + line.
    final offsets = points.map(at).toList();
    final line = Path()..moveTo(offsets.first.dx, offsets.first.dy);
    for (final o in offsets.skip(1)) {
      line.lineTo(o.dx, o.dy);
    }
    final area = Path.from(line)
      ..lineTo(offsets.last.dx, chart.bottom)
      ..lineTo(offsets.first.dx, chart.bottom)
      ..close();
    canvas.drawPath(area, Paint()..color = color.withValues(alpha: 0.08));
    canvas.drawPath(
      line,
      Paint()
        ..color = color
        ..strokeWidth = 2.5
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round,
    );

    // Observed points; the latest one emphasised.
    for (final o in offsets) {
      canvas.drawCircle(o, 3.2, Paint()..color = color);
    }
    canvas.drawCircle(offsets.last, 6, Paint()..color = Colors.white);
    canvas.drawCircle(offsets.last, 4.5, Paint()..color = color);
  }

  void _label(Canvas canvas, String text, Offset offset, {double width = 60, bool alignRight = false}) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: 10.5, color: Colors.grey.shade700)),
      textDirection: TextDirection.ltr,
      textAlign: alignRight ? TextAlign.right : TextAlign.left,
    )..layout(minWidth: width, maxWidth: width);
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(PriceTrendChartPainter old) => old.points != points || old.color != color;
}

/// One-line trend summary for list rows (e.g. Pending Collections).
class PriceTrendSummaryText extends StatelessWidget {
  final Future<PriceTrend> future;
  const PriceTrendSummaryText({super.key, required this.future});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PriceTrend>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done || snapshot.hasError) {
          return const SizedBox.shrink();
        }
        final trend = snapshot.data!;
        if (!trend.hasTrend) {
          return Text(
            '${context.tr('Price trend:')} ${context.tr('Not enough historical data yet.')}',
            key: const Key('pending_price_trend'),
          );
        }
        final style = _trendStyle(trend.trend);
        return Text(
          '${context.tr('Price trend:')} ${context.tr(style.label)}'
          '${trend.latestPricePerKg == null ? '' : ' · ${context.tr('Latest market price:')} ₹${trend.latestPricePerKg!.toStringAsFixed(2)}/kg'}',
          key: const Key('pending_price_trend'),
          style: TextStyle(color: style.color),
        );
      },
    );
  }
}
